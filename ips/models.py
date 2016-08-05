from django.core.validators import validate_ipv46_address
from django.db import models

from policies.models import Policy


class IP(models.Model):
    ip = models.CharField(
        max_length=40,
        verbose_name='IP Address',
        validators=[validate_ipv46_address],
        primary_key=True
    )
    check_name = models.CharField(
        max_length=255,
        unique=True,
    )
    weight = models.PositiveIntegerField(default=10)


class IPSet(models.Model):
    policy = models.OneToOneField(Policy)
    state = models.CharField(max_length=16)
    ip_set = models.ForeignKey(IP)
