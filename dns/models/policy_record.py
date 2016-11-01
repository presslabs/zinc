from django.conf import settings
from django.db import models
from hashid_field import HashidField

from dns.models import Policy, Zone


class PolicyRecord(models.Model):
    id = HashidField(
            editable=False,
            min_length=getattr(settings, 'HASHIDS_MIN_LENGTH', 7),
            primary_key=True
         )
    name = models.CharField(max_length=255, unique=True)
    policy = models.ForeignKey(Policy)
    dirty = models.BooleanField(default=True, editable=False)
    zone = models.ForeignKey(Zone)

    def __str__(self):
        return '{} {} {}'.format(self.name, self.policy, self.zone)

    def __unicode__(self):
        return self.__str__()
