from django.db import models

from ..utils import get_regions


class IP(models.Model):
    ip = models.GenericIPAddressField(
        primary_key=True,
        protocol='IPv4',
        verbose_name='IP Address'
    )

    provider = models.CharField(max_length=128, null=False)

    name = models.CharField(max_length=24, verbose_name='Name')
    location = models.CharField(max_length=32, verbose_name='Location')

    def __unicode__(self):
        return '{}: {} / {] / {}'.format(self.name, self.provider, self.location, self.ip)
