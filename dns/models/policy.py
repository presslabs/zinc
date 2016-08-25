from django.db import models
from django.db.models.signals import pre_save

from dns.models import PolicyMember


class Policy(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    modified_index = models.PositiveIntegerField(default=0, editable=False)

    members = models.ManyToManyField(PolicyMember)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.__str__()

    @staticmethod
    def modify_index(sender, instance, *args, **kwargs):
        instance.modified_index += 1

    class Meta:
        verbose_name_plural = 'policies'


pre_save.connect(Policy.modify_index, sender=Policy)
