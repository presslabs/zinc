from django.db import models
from dns.models import PolicyMember


class Policy(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    members = models.ManyToManyField(PolicyMember)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.__str__()

    class Meta:
        verbose_name_plural = 'policies'
