from django.db import models

from zones.models import Zone


class Domain(models.Model):
    name = models.CharField(
            max_length=255,
            unique=True
    )
    zone = models.OneToOneField(Zone)
