from django.db import models

from dns.models import Policy, Zone


class PolicyRecord(models.Model):
    name = models.CharField(max_length=255)
    policy = models.ForeignKey(Policy)
    dirty = models.BooleanField(default=True, editable=False)
    zone = models.ForeignKey(Zone)
