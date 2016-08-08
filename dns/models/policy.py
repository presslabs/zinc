from django.db import models

from dns.models import IP


class Policy(models.Model):
    name = models.CharField(max_length=255, unique=True, null=False)
    modified_index = models.PositiveIntegerField(default=0, editable=False)

    ip = models.ManyToManyField(IP)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'policies'
