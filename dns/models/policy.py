from django.conf import settings
from django.db import models
from hashid_field import HashidField

from dns.models import PolicyMember


class Policy(models.Model):
    id = HashidField(
            editable=False,
            min_length=getattr(settings, 'HASHIDS_MIN_LENGTH', 7),
            primary_key=True
         )
    name = models.CharField(max_length=255, unique=True, null=False)
    members = models.ManyToManyField(PolicyMember)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.__str__()

    class Meta:
        verbose_name_plural = 'policies'
