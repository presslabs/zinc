from collections import OrderedDict
import collections.abc
import contextlib
import json
import uuid
from logging import getLogger

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q

from zinc import ns_check, route53, tasks
from zinc.route53 import HealthCheck, get_local_aws_region_choices
from zinc.route53.record import RECORD_PREFIX
from zinc.validators import validate_domain, validate_hostname


logger = getLogger(__name__)

ROUTING_CHOICES = OrderedDict([
    ("latency", "latency"),
    ("weighted", "weighted"),
])


class IP(models.Model):
    ip = models.GenericIPAddressField(
        primary_key=True,
        protocol='IPv4',
        verbose_name='IP Address'
    )
    hostname = models.CharField(max_length=64, validators=[validate_hostname])
    friendly_name = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    healthcheck_id = models.CharField(max_length=200, blank=True, null=True)
    healthcheck_caller_reference = models.UUIDField(null=True, blank=True)
    deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'IP'

    def mark_policy_records_dirty(self):
        # sadly this breaks sqlite
        # policies = [
        #     member.policy for member in
        #     self.policy_members.order_by('policy_id').distinct('policy_id')]
        policies = set([
            member.policy for member in
            self.policy_members.all()])
        for policy in policies:
            policy.mark_policy_records_dirty()

    def soft_delete(self):
        self.deleted = True
        self.enabled = False
        self.save(update_fields=['deleted', 'enabled'])
        self.reconcile_healthcheck()

    def reconcile_healthcheck(self):
        HealthCheck(self).reconcile()

    def __str__(self):
        value = self.friendly_name or self.hostname.split(".", 1)[0]
        return '{} ({})'.format(self.ip, value)


class Policy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, null=False)
    routing = models.CharField(
        max_length=255, choices=ROUTING_CHOICES.items(), default=ROUTING_CHOICES['latency'])

    dirty_trigger_fields = set(['name'])

    class Meta:
        verbose_name_plural = 'policies'
        ordering = ('name',)

    def __str__(self):
        return self.name

    def change_trigger(self, field_names):
        # if field_names is not a set-like object (eg. dict_keys) convert to set
        if not isinstance(field_names, collections.abc.Set):
            field_names = set(field_names)
        if field_names & self.dirty_trigger_fields:
            self.mark_policy_records_dirty()

    # atomic isn't strictly required since it's a single statement that would run
    # in a transaction in autocommit mode on innodb, but it's better to be explicit
    @transaction.atomic
    def mark_policy_records_dirty(self):
        self.records.update(dirty=True)


class PolicyMember(models.Model):
    AWS_REGIONS = get_local_aws_region_choices()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.CharField(choices=AWS_REGIONS, max_length=20,
                              default='us-east-1')
    ip = models.ForeignKey(IP, on_delete=models.CASCADE, related_name='policy_members')
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='members')
    weight = models.PositiveIntegerField(default=10)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ('region', 'ip__hostname')

    def save(self, *args, **kwargs):
        self.policy.mark_policy_records_dirty()
        return super(PolicyMember, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.policy.mark_policy_records_dirty()
        return super(PolicyMember, self).delete(*args, **kwargs)

    def __str__(self):
        return '{} {} {}'.format(self.ip, self.region, self.weight)


def validate_json(value):
    try:
        json.loads(value)
    except json.JSONDecodeError:
        raise ValidationError("Not valid json")


class Zone(models.Model):
    root = models.CharField(max_length=255, validators=[validate_domain])
    route53_id = models.CharField(max_length=32, unique=True, editable=False,
                                  null=True, default=None)
    caller_reference = models.UUIDField(editable=False, null=True)
    deleted = models.BooleanField(default=False)
    ns_propagated = models.BooleanField(default=False)
    cached_ns_records = models.TextField(validators=[validate_json], default=None, null=True)

    class Meta:
        ordering = ['root']

    def __init__(self, *args, **kwargs):
        self._route53_instance = None
        super(Zone, self).__init__(*args, **kwargs)

    @property
    def dirty(self):
        dirty = False
        for policy_record in self.policy_records.all():
            dirty |= policy_record.dirty

        return dirty

    def clean(self):
        # if the root is not a fqdn then add the dot at the end
        # this will be called from admin
        if not self.root.endswith('.'):
            self.root += '.'
        super().clean()

    def save(self, *args, **kwargs):
        if self.route53_id is not None:
            if self.route53_id.startswith('/hostedzone/'):
                self.route53_id = self.route53_id[len('/hostedzone/'):]
        return super(Zone, self).save(*args, **kwargs)

    def commit(self):
        self.r53_zone.commit()

    def delete_record_by_hash(self, record_hash):
        records = self.r53_zone.records()
        to_delete_record = records[record_hash]
        to_delete_record.deleted = True
        self.r53_zone.process_records([to_delete_record])

    def delete_record(self, record):
        self.delete_record_by_hash(record.id)

    def get_policy_records(self):
        # return a list with Policy records
        records = []
        for policy_record in self.policy_records.all():
            records.append(policy_record.serialize())

        return records

    @property
    def r53_zone(self):
        if not self._route53_instance:
            self._route53_instance = route53.Zone(self)
        return self._route53_instance

    def soft_delete(self):
        self.deleted = True
        self.save(update_fields=['deleted'])
        tasks.aws_delete_zone.delay(self.pk)

    @property
    def records(self):
        records = self.r53_zone.records()
        filtered_records = []
        policy_records = self.get_policy_records()

        for record in records.values():
            if record.is_hidden:
                continue
            if record.is_alias and any(((record.name == pr.name) for pr in policy_records)):
                continue
            filtered_records.append(record)

        # Add policy records.
        for record in policy_records:
            filtered_records.append(record)

        return filtered_records

    def update_records(self, records):
        self.r53_zone.process_records(records)

    def __str__(self):
        return '{} ({})'.format(self.root, self.route53_id)

    @transaction.atomic
    def reconcile(self):
        self.r53_zone.reconcile()

    @contextlib.contextmanager
    @transaction.atomic
    def lock_dirty_policy_records(self):
        policy_records = self.policy_records.select_for_update() \
                             .select_related('policy').filter(dirty=True)
        yield policy_records

    def _delete_orphaned_managed_records(self):
        """Delete any managed record not belonging to one of the zone's policies"""
        policies = set([pr.policy for pr in self.policy_records.select_related('policy')])
        pol_names = ['{}_{}'.format(RECORD_PREFIX, policy.name) for policy in policies]
        for record in self.r53_zone.records().values():
            name = record.name
            if name.startswith(RECORD_PREFIX):
                for pol_name in pol_names:
                    if name.startswith(pol_name):
                        break
                else:
                    self.delete_record(record)

    @classmethod
    def update_ns_propagated(cls, delay=0):
        resolver = ns_check.get_resolver()
        # the order matters because we want unpropagated zones to be checked first
        # to minimize the delay in tarnsitioning to propagated state
        for zone in cls.objects.order_by('ns_propagated').all():
            try:
                zone.ns_propagated = ns_check.is_ns_propagated(
                    zone, resolver=resolver, delay=delay)
            except ns_check.CouldNotResolve:
                logger.warn('Failed to resolve nameservers for %s', zone.root)
            else:
                if not zone.ns_propagated:
                    logger.info('ns_propagated %-5s %s', zone.ns_propagated, zone.root)
                zone.save()

    @classmethod
    def _dirty_query(cls):
        return Q(deleted=True) | Q(route53_id=None) | Q(policy_records__dirty=True)

    @classmethod
    def need_reconciliation(cls):
        return cls.objects.filter(
            cls._dirty_query()
        )

    @classmethod
    def get_clean_zones(cls):
        return cls.objects.filter(
            ~cls._dirty_query()
        )


class PolicyRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    policy = models.ForeignKey(Policy, related_name='records')
    dirty = models.BooleanField(default=True, editable=False)
    zone = models.ForeignKey(Zone, related_name='policy_records')
    deleted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('name', 'zone')

    def __init__(self, *a, **kwa):
        super().__init__(*a, **kwa)
        self._r53_policy_record = None

    def __str__(self):
        return '{}.{}'.format(self.name, self.zone.root)

    def serialize(self):
        assert self.zone is not None
        record = route53.PolicyRecord(policy_record=self, zone=self.zone.r53_zone)
        record.dirty = self.dirty
        record.managed = False
        record.deleted = self.deleted
        return record

    def soft_delete(self):
        self.deleted = True
        self.dirty = True
        self.save(update_fields=['deleted', 'dirty'])

    def mark_dirty(self):
        self.dirty = True
        self.save(update_fields=['dirty'])

    def clean(self):
        zone_records = self.zone.r53_zone.records()
        # guard against PolicyRecords/CNAME name clashes
        if not self.deleted:
            # don't do the check unless the PR is deleted
            for record in zone_records.values():
                if record.name == self.name and record.type == 'CNAME':
                    raise ValidationError(
                        {'name': "A CNAME record of the same name already exists."})

        super().clean()

    @property
    def r53_policy_record(self):
        if self._r53_policy_record is None:
            self._r53_policy_record = route53.PolicyRecord(
                policy_record=self, zone=self.zone.r53_zone)
        return self._r53_policy_record

    @transaction.atomic
    def apply_record(self):
        # build the tree for this policy record.
        if self.deleted:
            # if the zone is marked as deleted don't try to build the tree.
            self.delete_record()
            self.delete()
            return

        self.zone.r53_zone.process_records([self.r53_policy_record])

        self.dirty = False  # mark as clean
        self.save()

    @classmethod
    def new_or_deleted(cls, name, zone):
        # if the record hasn't been reconciled yet (still exists in the DB), we want to reuse it
        # to avoid violating the unique together constraint on name and zone
        # TODO: if we add deleted to that constraint and make it null-able, we can keep the DB
        # sane and simplify the system. Reusing the record like this opens up the possibility
        # of running into concurrency issues.
        try:
            model = cls.objects.get(deleted=True, name=name, zone=zone)
            model.deleted = False
            return model
        except cls.DoesNotExist:
            return cls(name=name, zone=zone)
