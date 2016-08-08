from django.db import models

from zones.models import Zone
from policies.models import Policy


class Domain(models.Model):
    name = models.CharField(max_length=255, unique=True)
    zone = models.ForeignKey(Zone)
    policy = models.ForeignKey(Policy)
