import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import SuspiciousOperation

from dns.utils import route53
from dns.utils.route53 import get_local_aws_regions, HealthCheck
from dns.validators import validate_domain, validate_hostname
from zinc.vendors import hashids
from dns import tasks
from zinc import POLICY_ROUTED


RECORD_PREFIX = '_zn'


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
    healthcheck_caller_reference = models.UUIDField(null=True)

    def save(self, *a, **kwa):
        if self.friendly_name == "":
            self.friendly_name = self.hostname.split(".", 1)[0]
        super().save(*a, **kwa)

    def reconcile_healthcheck(self):
        healthcheck = HealthCheck(self).reconcile()

    def __str__(self):
        value = self.friendly_name or self.hostname
        return '{} {}'.format(self.ip, value)


class Policy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, null=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'policies'

    @transaction.atomic
    def apply_policy(self, zone):
        for policy_member in self.members.all():
            zone.add_record({
                'name': '{}_{}.{}'.format(RECORD_PREFIX, self.name, policy_member.region),
                'ttl': 30,
                'type': 'A',
                'values': [policy_member.ip.ip],
                'SetIdentifier': '{}-{}'.format(str(policy_member.id), policy_member.region),
                'Weight': policy_member.weight,
                # 'HealthCheckId': str(policy_member.healthcheck_id),
            })

        # TODO: check for rigon for all ips down
        regions = set([pm.region for pm in self.members.all()])
        for region in regions:
            zone.add_record({
                'name': '{}_{}'.format(RECORD_PREFIX, self.name),
                'type': 'A',
                'AliasTarget': {
                    'HostedZoneId': zone.route53_zone.id,
                    'DNSName': '{}_{}.{}'.format(RECORD_PREFIX, self.name, region),
                    'EvaluateTargetHealth': len(regions) > 1
                },
                'Region': region,
                'SetIdentifier': region,
            })

        zone.save()
        return regions

    def delete_policy(self, zone):
        records = zone.route53_zone.records()

        # If the policy is in used by another record then don't delete it.
        policy_records = zone.policy_records.filter(policy=self)
        if len(policy_records) > 1:
            return

        regions = set([pm.region for pm in self.members.all()])
        for region in regions:
            zone.delete_record({
                'name': '{}_{}'.format(RECORD_PREFIX, self.name),
                'type': 'A',
                'AliasTarget': {},  # Not need to be specified.
                'SetIdentifier': region,
            })

        for policy_member in self.members.all():
            zone.delete_record({
                'name': '{}_{}.{}'.format(RECORD_PREFIX, self.name, policy_member.region),
                'type': 'A',
                'SetIdentifier': '{}-{}'.format(str(policy_member.id), policy_member.region),
            })


class PolicyMember(models.Model):
    AWS_REGIONS = [(region, region) for region in get_local_aws_regions()]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    region = models.CharField(choices=AWS_REGIONS, max_length=20)
    ip = models.ForeignKey(IP, on_delete=models.CASCADE)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='members')
    healthcheck_id = models.IntegerField(editable=False, null=True)
    weight = models.PositiveIntegerField(default=10)

    def __str__(self):
        return '{} {} {}'.format(self.ip, self.region, self.weight)


class Zone(models.Model):
    root = models.CharField(max_length=255, validators=[validate_domain])
    route53_id = models.CharField(max_length=32, unique=True, editable=False,
                                  null=True, default=None)
    caller_reference = models.UUIDField(default=uuid.uuid4)
    deleted = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs):
        self._route53_instance = None
        super(Zone, self).__init__(*args, **kwargs)

    @property
    def dirty(self):
        dirty = False
        for policy_record in self.policy_records.all():
            dirty |= policy_record.dirty

        return dirty

    def save(self, *args, **kwargs):
        if self.route53_id is not None:
            if self.route53_id.startswith('/hostedzone/'):
                self.route53_id = self.route53_id[len('/hostedzone/'):]
            self.route53_zone.commit()
        return super(Zone, self).save(*args, **kwargs)

    def add_record(self, record):
        # Add record if is POLICY_ROUTED then create one and add it.
        # else add to aws zone.
        # Return record hash or policy record id.
        if record['type'] == POLICY_ROUTED:
            try:
                policy = Policy.objects.get(id=record['values'][0])
            except Policy.DoesNotExist:
                # Return 400
                raise SuspiciousOperation('Policy \'{}\'  does not exists.'.format(
                    record['values'][0]))
            try:
                policy_record = self.policy_records.get(name=record['name'])
                if record.get('delete', False):
                    policy_record.deleted = True
                else:
                    policy_record.policy = policy
                policy_record.dirty = True
            except PolicyRecord.DoesNotExist:
                policy_record = PolicyRecord(name=record['name'], policy=policy, zone=self)

            policy_record.save()
            return policy_record.serialize(zone=self)
        else:
            record_hash = hashids.encode_record(record, self.route53_zone.id)
            self.route53_zone.add_record_changes(record, key=record_hash)
            return record

    def delete_record_by_hash(self, record_hash):
        records = self.route53_zone.records()
        if record_hash not in records:
            # trying to delete a nonexistent record
            return
        to_delete_record = records[record_hash]
        to_delete_record['delete'] = True
        self.route53_zone.add_record_changes(to_delete_record, key=record_hash)

    def delete_record(self, record):
        self.delete_record_by_hash(hashids.encode_record(record, self.route53_zone.id))

    def get_policy_records(self):
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
            record['zone_id'] = self.id
            if record['name'].startswith(RECORD_PREFIX):
                continue
            if ('AliasTarget' in record):
                if self.policy_records.filter(name=record['name']).exists():
                    continue
                # if the record is ALIAS then translate it to ALIAS type known by API
                record['values'] = ['ALIAS {}.{}'.format(record['AliasTarget']['DNSName'],
                                                         self.root)]
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
        return '{} {}'.format(self.pk, self.root)


class PolicyRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    policy = models.ForeignKey(Policy)
    dirty = models.BooleanField(default=True, editable=False)
    zone = models.ForeignKey(Zone, related_name='policy_records')
    deleted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('name', 'zone')

    def __str__(self):
        return '{} {} {}'.format(self.name, self.policy, self.zone)

    def serialize(self, zone):
        return {
            'name': self.name,
            'type': POLICY_ROUTED,
            'values': [str(self.policy.id)],
            'dirty': self.dirty,
            'manage': False,
            'deleted': self.deleted,
            'id': hashids.encode_record({
                'name': self.name,
                'type': POLICY_ROUTED
            }, zone.route53_zone.id)
        }

    @transaction.atomic
    def apply_record(self):
        if self.deleted:
            return

        if self.policy.apply_policy(self.zone):
            self.zone.add_record({
                'name': self.name,
                'type': 'A',
                'AliasTarget': {
                    'HostedZoneId': self.zone.route53_zone.id,
                    'DNSName': '{}_{}'.format(RECORD_PREFIX, self.policy.name),
                    'EvaluateTargetHealth': False
                },
            })

        self.zone.save()
        self.dirty = False
        self.save()

    def delete_record(self):
        self.zone.delete_record({
            'name': self.name,
            'type': 'A',
            'AliasTarget': {},
        })
        self.policy.delete_policy(self.zone)
        self.zone.save()
