from django.db import models

from . import Zone, Policy


class Domain(models.Model):
    name = models.CharField(max_length=255, unique=True)
    zone = models.ForeignKey(Zone)
    policy = models.ForeignKey(Policy)

    def __unicode__(self):
        return self.name
