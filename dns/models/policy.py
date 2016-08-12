from django.db import models
from django.db.models.signals import pre_save

from . import PolicyMember


class Policy(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    modified_index = models.PositiveIntegerField(default=0, editable=False)

    members = models.ManyToManyField(PolicyMember)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'policies'


def modify_index(sender, instance, *args, **kwargs):
    instance.modified_index += 1


pre_save.connect(modify_index, sender=Policy)
