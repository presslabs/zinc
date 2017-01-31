import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from dns.tasks import aws_delete_zone
from dns.utils import route53
from dns.utils.route53 import get_local_aws_regions
from dns.validators import validate_domain, validate_hostname


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

    def __unicode__(self):
        return self.__str__()


class Policy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, null=False)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.__str__()

    class Meta:
        verbose_name_plural = 'policies'


class PolicyMember(models.Model):
    AWS_REGIONS = [(region, region) for region in get_local_aws_regions()]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.CharField(choices=AWS_REGIONS, max_length=20)
    ip = models.ForeignKey(IP, on_delete=models.CASCADE)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE, related_name='members')
    healthcheck_id = models.IntegerField(editable=False, null=True)
    weight = models.PositiveIntegerField(default=10)

    def __str__(self):
        return '{} {} {}'.format(self.ip, self.location, self.weight)

    def __unicode__(self):
        return self.__str__()


class Zone(models.Model):
    root = models.CharField(max_length=255, validators=[validate_domain])
    route53_id = models.CharField(max_length=32, unique=True, editable=False)
    caller_reference = models.CharField(max_length=32, editable=False,
                                        unique=True)

    def __init__(self, *args, **kwargs):
        self._route53_instance = None
        super(Zone, self).__init__(*args, **kwargs)

    def clean(self):
        # TODO: this probably should be in save
        if self.route53_id is not None:
            return
        try:
            zone = route53.Zone.create(self.root)
        except route53.ClientError as e:
            raise ValidationError(str(e), 400)

        self.route53_id = zone.id
        self.caller_reference = zone.caller_reference

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
        for key, record in records.items():
            self.route53_zone.add_record_changes(record, key=key)
        self.route53_zone.commit()

    def __str__(self):
        return '{} {}'.format(self.pk, self.root)

    def __unicode__(self):
        return self.__str__()


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
    zone = models.ForeignKey(Zone)

    def __str__(self):
        return '{} {} {}'.format(self.name, self.policy, self.zone)

    def __unicode__(self):
        return self.__str__()
