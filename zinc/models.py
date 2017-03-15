import collections.abc
import uuid
from logging import getLogger

from django.db import models, transaction
from django.core.exceptions import SuspiciousOperation, ValidationError

from django_project import POLICY_ROUTED
from django_project.vendors import hashids
from zinc import ns_check, route53, tasks
from zinc.route53 import HealthCheck, get_local_aws_region_choices
from zinc.validators import validate_domain, validate_hostname

RECORD_PREFIX = '_zn'
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

    @transaction.atomic
    def apply_policy(self, zone):
        # first delete the existing policy
        self._remove_tree(zone)
        records, _ = self._build_tree(zone)
        zone.records = records
        zone.commit()

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
        for _, record in zone.route53_zone.records().items():
            if record['name'].startswith('{}_{}'.format(RECORD_PREFIX, self.name)):
                record['delete'] = True
                to_delete_records.append(record)
        zone.records = to_delete_records

    def _build_weighted_tree(self, policy_members, region_suffixed=True):
        # Build simple tree
        records = []
        for policy_member in policy_members:
            health_check = {}
            if policy_member.ip.healthcheck_id:
                health_check['HealthCheckId'] = str(policy_member.ip.healthcheck_id)
            record = {
                'ttl': 30,
                'type': 'A',
                'values': [policy_member.ip.ip],
                'SetIdentifier': '{}-{}'.format(str(policy_member.id), policy_member.region),
                'Weight': policy_member.weight,
                **health_check
            }
            if region_suffixed:
                record['name'] = '{}_{}_{}'.format(RECORD_PREFIX, self.name, policy_member.region)
            else:
                record['name'] = '{}_{}'.format(RECORD_PREFIX, self.name)
            records.append(record)

        return records

    def _build_lbr_tree(self, zone, policy_members):
        # Build latency based routed tree
        records = self._build_weighted_tree(policy_members)
        regions = set([pm.region for pm in policy_members])
        for region in regions:
            record = {
                'name': '{}_{}'.format(RECORD_PREFIX, self.name),
                'type': 'A',
                'AliasTarget': {
                    'HostedZoneId': zone.route53_zone.id,
                    'DNSName': '{}_{}_{}.{}'.format(RECORD_PREFIX, self.name, region, zone.root),
                    'EvaluateTargetHealth': True  # len(regions) > 1
                },
                'Region': region,
                'SetIdentifier': region,
            }
            records.append(record)
        return records

    def _build_tree(self, zone):
        # build the tree base for the provided zone
        policy_members = self.members.exclude(weight=0).exclude(ip__enabled=False)
        regions = set([pm.region for pm in policy_members])
        if len(regions) > 1:
            # Here is the case where are multiple regions
            records = self._build_lbr_tree(zone, policy_members)
        elif len(regions) == 1:
            # Case with a single region
            records = self._build_weighted_tree(policy_members, region_suffixed=False)
        else:
            # no policy record applied
            # should raise an error or log this
            raise Exception(
                "Policy can't be applied. zone: '{}'; policy: '{}'".format(
                    zone, self
                )
            )
        return records, regions


class PolicyMember(models.Model):
    AWS_REGIONS = get_local_aws_region_choices()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.CharField(choices=AWS_REGIONS, max_length=20,
                              default='us-east-1')
    ip = models.ForeignKey(IP, on_delete=models.CASCADE, related_name='policy_members')
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='members')
    weight = models.PositiveIntegerField(default=10)

    class Meta:
        ordering = ('region', 'ip__hostname')

    def save(self, *args, **kwargs):
        self.policy.mark_policy_records_dirty()
        return super(PolicyMember, self).save(*args, **kwargs)

    def __str__(self):
        return '{} {} {}'.format(self.ip, self.region, self.weight)


class Zone(models.Model):
    root = models.CharField(max_length=255, validators=[validate_domain])
    route53_id = models.CharField(max_length=32, unique=True, editable=False,
                                  null=True, default=None)
    caller_reference = models.UUIDField(editable=False, null=True)
    deleted = models.BooleanField(default=False)
    ns_propagated = models.BooleanField(default=False)

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
        if record['type'] == POLICY_ROUTED:
            try:
                policy = Policy.objects.get(id=record['values'][0])
            except Policy.DoesNotExist:
                # Policy don't exists. Return 400
                raise SuspiciousOperation('Policy \'{}\'  does not exists.'.format(
                    record['values'][0]))
            try:
                # update the policy record. Or delete or update policy.
                policy_record = self.policy_records.get(name=record['name'])
                if record.get('delete', False):
                    # The record will be deleted
                    policy_record.deleted = True
                else:
                    # Update policy for this record.
                    policy_record.policy = policy
                policy_record.dirty = True
            except PolicyRecord.DoesNotExist:
                # Policy don't exists so create one.
                if record.get('delete', False):
                    return None  # trying to delete a nonexisting POLICY_RECORD.
                policy_record = PolicyRecord(name=record['name'], policy=policy, zone=self)
                policy_record.full_clean()

            policy_record.save()
            return policy_record.serialize(zone=self)
        else:
            # This is a normal record. Forward it to route53 utils.
            self.route53_zone.add_records([record])
            return record

    def delete_record_by_hash(self, record_hash):
        records = self.route53_zone.records()
        if record_hash not in records:
            # trying to delete a nonexistent record. skip
            return
        to_delete_record = records[record_hash]
        to_delete_record['delete'] = True
        self.route53_zone.add_records([to_delete_record])

    def delete_record(self, record):
        self.delete_record_by_hash(hashids.encode_record(record, self.route53_zone.id))

    def get_policy_records(self):
        # return a list with Policy records
        records = []
        for policy_record in self.policy_records.all():
            records.append(policy_record.serialize(zone=self))

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

        # Hide all records that starts with the RECORD_PREFIX.
        # Translate policy records.
        for record_hash, record in records.items():
            record['id'] = record_hash
            if record['name'].startswith(RECORD_PREFIX):
                continue
            if ('AliasTarget' in record):
                if self.policy_records.filter(name=record['name']).exists():
                    continue
                # if the record is ALIAS then translate it to ALIAS type known by API
                record['values'] = ['ALIAS {}'.format(record['AliasTarget']['DNSName'])]
            filtered_records.append(record)

        for record in self.get_policy_records():
            record['zone_id'] = self.id
            filtered_records.append(record)

        return filtered_records

    @records.setter
    def records(self, records):
        for record in records:
            self.add_record(record)

    def __str__(self):
        return '{} ({})'.format(self.root, self.route53_id)

    def reconcile(self):
        self.route53_zone.reconcile()

    @transaction.atomic
    def build_tree(self):
        policy_records = self.policy_records.select_for_update() \
                             .select_related('policy').filter(dirty=True)
        dirty_policies = set([policy_record.policy for policy_record in policy_records])
        for policy in dirty_policies:
            policy.apply_policy(self)

        for policy_record in policy_records:
            policy_record.apply_record()

        self._delete_orphaned_managed_records()
        self.commit()

    def _delete_orphaned_managed_records(self):
        """Delete any managed record not belonging to one of the zone's policies"""
        policies = set([pr.policy for pr in self.policy_records.select_related('policy')])
        pol_names = ['{}_{}'.format(RECORD_PREFIX, policy.name) for policy in policies]
        for record in self.route53_zone.records().values():
            name = record['name']
            if name.startswith(RECORD_PREFIX):
                for pol_name in pol_names:
                    if name.startswith(pol_name):
                        break
                else:
                    self.delete_record(record)

    @classmethod
    def update_ns_propagated(cls):
        resolver = ns_check.get_resolver()
        for zone in cls.objects.order_by('ns_propagated').all():
            try:
                zone.ns_propagated = ns_check.is_ns_propagated(zone, resolver=resolver)
            except ns_check.CouldNotResolve:
                logger.warn('Failed to resolve nameservers for %s', zone.root)
            else:
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

    def __str__(self):
        return '{}.{}'.format(self.name, self.zone.root)

    def serialize(self, zone):
        return {
            'name': self.name,
            'fqdn': '{}.{}'.format(self.name, self.zone.root),
            'type': POLICY_ROUTED,
            'values': [str(self.policy.id)],
            'ttl': None,
            'dirty': self.dirty,
            'manage': False,
            'deleted': self.deleted,
            'id': hashids.encode_record({
                'name': self.name,
                'type': POLICY_ROUTED
            }, zone.route53_zone.id)
        }

    def soft_delete(self):
        self.deleted = True
        self.dirty = True
        self.save(update_fields=['deleted', 'dirty'])

    def clean(self):
        zone_records = self.zone.route53_zone.records()
        for record in zone_records.values():
            if record['name'] == self.name and record['type'] == 'CNAME':
                raise ValidationError({'name': "A CNAME record of the same name already exists."})

        super().clean()

    @transaction.atomic
    def apply_record(self):
        # build the tree for this policy record.
        if self.deleted:
            # if the zone is marked as deleted don't try to build the tree.
            return

        self.zone.add_record({
            'name': self.name,
            'type': 'A',
            'AliasTarget': {
                'HostedZoneId': self.zone.route53_zone.id,
                'DNSName': '{}_{}.{}'.format(RECORD_PREFIX, self.policy.name, self.zone.root),
                'EvaluateTargetHealth': False
            },
        })

        self.dirty = False  # mark as clean
        self.save()

    def delete_record(self):
        # delete the tree.
        self.zone.delete_record({
            'name': self.name,
            'type': 'A',
            'AliasTarget': {},
        })
        self.policy.delete_policy(self.zone)
        self.zone.commit()
