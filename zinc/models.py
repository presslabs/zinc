import collections.abc
import contextlib
import json
import uuid
from logging import getLogger
import warnings

from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db import models, transaction

from zinc import ns_check, route53, tasks
from zinc.route53 import HealthCheck, get_local_aws_region_choices
from zinc.route53.record import POLICY_ROUTED, RECORD_PREFIX
from zinc.validators import validate_domain, validate_hostname


logger = getLogger(__name__)


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

    # @transaction.atomic
    # def apply_policy(self, zone):
    #     # first delete the existing policy
    #     self._remove_tree(zone)
    #     records, _ = self._build_tree(zone)
    #     zone.update_records(records)
    #     zone.commit()

    @transaction.atomic
    def delete_policy(self, zone):
        # If the policy is in used by another record then don't delete it.
        policy_records = zone.policy_records.filter(policy=self)
        if len(policy_records) > 1:
            return
        self._remove_tree(zone)
        zone.commit()

    def _remove_tree(self, zone):
        to_delete_records = []
        for record in zone.route53_zone.records().values():
            if record.is_member_of(policy=self):
                record.deleted = True
                to_delete_records.append(record)
        zone.update_records(to_delete_records)


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
        self.route53_zone.commit()

    def add_record(self, record):
        # Add record if is POLICY_ROUTED then create one and add it.
        # else add to aws zone.
        # Return record hash or policy record id.
        if record.is_policy_record:
            return self.upsert_policy_record(record)
        else:
            self.route53_zone.add_records([record])
            return record

    def upsert_policy_record(self, record):
        try:
            policy = Policy.objects.get(id=record.values[0])
        except Policy.DoesNotExist:
            # Policy don't exists. Return 400
            raise SuspiciousOperation('Policy \'{}\'  does not exists.'.format(
                record.values[0]))
        try:
            # update the policy record. Or delete or update policy.
            policy_record = self.policy_records.get(name=record.name)
            if record.deleted:
                # The record will be deleted
                policy_record.deleted = True
            else:
                # Update policy for this record.
                policy_record.policy = policy
                policy_record.deleted = False  # clear deleted flag
            policy_record.dirty = True
        except PolicyRecord.DoesNotExist:
            # Policy don't exists so create one.
            if record.deleted:
                return None  # trying to delete a nonexisting POLICY_RECORD.
            policy_record = PolicyRecord(name=record.name, policy=policy, zone=self)
            policy_record.full_clean()

        policy_record.save()
        return policy_record.serialize()

    def delete_record_by_hash(self, record_hash):
        records = self.route53_zone.records()
        if record_hash not in records:
            # trying to delete a nonexistent record. skip
            raise Exception("cocos")
        to_delete_record = records[record_hash]
        to_delete_record.deleted = True
        self.route53_zone.add_records([to_delete_record])

    def delete_record(self, record):
        self.delete_record_by_hash(record.id)

    def get_policy_records(self):
        # return a list with Policy records
        records = []
        for policy_record in self.policy_records.all():
            records.append(policy_record.serialize())

        return records

    @property
    def route53_zone(self):
        if not self._route53_instance:
            self._route53_instance = route53.Zone(self)
        return self._route53_instance

    def soft_delete(self):
        self.deleted = True
        self.save(update_fields=['deleted'])
        tasks.aws_delete_zone.delay(self.pk)

    @property
    def records(self):
        records = self.route53_zone.records()
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
            # record.zone_id = self.route53_id
            filtered_records.append(record)

        return filtered_records

    def update_records(self, records):
        self.route53_zone.add_records(records)

    def __str__(self):
        return '{} ({})'.format(self.root, self.route53_id)

    def reconcile(self):
        self.route53_zone.reconcile()

    @contextlib.contextmanager
    @transaction.atomic
    def lock_dirty_policy_records(self):
        policy_records = self.policy_records.select_for_update() \
                             .select_related('policy').filter(dirty=True)
        yield policy_records

    # @transaction.atomic
    # def build_tree(self):
    #     self.route53_zone._reconcile_policy_records()
    #     policy_records = self.policy_records.select_for_update() \
    #                          .select_related('policy').filter(dirty=True)
    #     # dirty_policies = set([policy_record.policy for policy_record in policy_records])
    #     # for policy in dirty_policies:
    #     #     r53_policy = route53.Policy(policy=policy, zone=self.route53_zone)
    #     #     r53_policy.reconcile()
    #     #     # policy.apply_policy(self)

    #     for policy_record in policy_records:
    #         # policy_record.apply_record()
    #         policy_record.r53_policy_record.reconcile()

    #     self._delete_orphaned_managed_records()
    #     self.commit()

    def _delete_orphaned_managed_records(self):
        """Delete any managed record not belonging to one of the zone's policies"""
        policies = set([pr.policy for pr in self.policy_records.select_related('policy')])
        pol_names = ['{}_{}'.format(RECORD_PREFIX, policy.name) for policy in policies]
        for record in self.route53_zone.records().values():
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
        # return route53.PolicyRecord(policy_record=self, zone=self.zone.route53_zone)
        return route53.Record(
            name=self.name,
            type=POLICY_ROUTED,
            values=[str(self.policy.id)],
            ttl=None,
            dirty=self.dirty,
            managed=False,
            deleted=self.deleted,
            zone=self.zone.route53_zone,
        )

    def soft_delete(self):
        self.deleted = True
        self.dirty = True
        self.save(update_fields=['deleted', 'dirty'])

    def clean(self):
        zone_records = self.zone.route53_zone.records()
        for record in zone_records.values():
            if record.name == self.name and record.type == 'CNAME':
                raise ValidationError({'name': "A CNAME record of the same name already exists."})

        super().clean()

    @property
    def r53_policy_record(self):
        if self._r53_policy_record is None:
            self._r53_policy_record = route53.PolicyRecord(
                policy_record=self, zone=self.zone.route53_zone)
        return self._r53_policy_record

    @transaction.atomic
    def apply_record(self):
        # build the tree for this policy record.
        if self.deleted:
            # if the zone is marked as deleted don't try to build the tree.
            self.delete_record()
            self.delete()
            return

        self.zone.route53_zone.add_records([self.r53_policy_record])

        self.dirty = False  # mark as clean
        self.save()

    def delete_record(self):
        # delete the tree.
        self.r53_policy_record.deleted = True
        self.zone.route53_zone.add_records([self.r53_policy_record])
        self.policy.delete_policy(self.zone)
        self.zone.commit()
