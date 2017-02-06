import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db import transaction

from dns.tasks import aws_delete_zone
from dns.utils import route53
from dns.utils.route53 import get_local_aws_regions
from dns.validators import validate_domain, validate_hostname
from zinc.vendors import hashids


class IP(models.Model):
    ip = models.GenericIPAddressField(
        primary_key=True,
        protocol='IPv4',
        verbose_name='IP Address'
    )
    hostname = models.CharField(max_length=64, validators=[validate_hostname])
    friendly_name = models.TextField(blank=True)

    enabled = models.BooleanField(default=True)

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
                'name': '_{}.{}'.format(self.name, policy_member.region),
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
                'name': '_{}'.format(self.name),
                'type': 'A',
                'AliasTarget': {
                    'HostedZoneId': zone.route53_zone.id,
                    'DNSName': '_{}.{}'.format(self.name, region),
                    'EvaluateTargetHealth': len(regions) > 1
                },
                'Region': region,
                'SetIdentifier': region,
            })

        zone.save()
        return regions


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
    route53_id = models.CharField(max_length=32, unique=True, editable=False)
    caller_reference = models.CharField(max_length=32, editable=False,
                                        unique=True)

    def __init__(self, *args, **kwargs):
        self._route53_instance = None
        super(Zone, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.route53_id is not None:
            self.route53_zone.commit()
            return super(Zone, self).save(*args, **kwargs)

        try:
            zone = route53.Zone.create(self.root)
        except route53.ClientError as e:
            raise ValidationError(str(e), 400)

        self.route53_id = zone.id
        self.caller_reference = zone.caller_reference

        return super(Zone, self).save(*args, **kwargs)

    def add_record(self, record):
        self.route53_zone.add_record_changes(record, key=hashids.encode_record(record))

    @property
    def route53_zone(self):
        if not self._route53_instance:
            self._route53_instance = route53.Zone(id=self.route53_id, root=self.root)

        return self._route53_instance

    @property
    def records(self):
        return self.route53_zone.records()

    @records.setter
    def records(self, records):
        self.route53_zone.add_records(records)

    def __str__(self):
        return '{} {}'.format(self.pk, self.root)


@receiver(post_delete, sender=Zone)
def aws_delete(instance, **kwargs):
    if 'raw' in kwargs and kwargs['raw']:
        return
    aws_delete_zone.delay(instance.route53_id, instance.root)


class PolicyRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    policy = models.ForeignKey(Policy)
    dirty = models.BooleanField(default=True, editable=False)
    zone = models.ForeignKey(Zone, related_name='policy_records')

    def __str__(self):
        return '{} {} {}'.format(self.name, self.policy, self.zone)

    @transaction.atomic
    def apply_record(self):
        if self.policy.apply_policy(self.zone):
            self.zone.add_record({
                'name': self.name,
                'type': 'A',
                'AliasTarget': {
                    'HostedZoneId': self.zone.route53_zone.id,
                    'DNSName': '_{}'.format(self.policy.name),
                    'EvaluateTargetHealth': False
                }
            })

        self.zone.save()
        self.dirty = False
        self.save()
