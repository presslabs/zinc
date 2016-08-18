from django.db import models

from zinc.vendors.lattice import lattice


class IP(models.Model):
    providers = [p['provider'].split('.')[2] for p in lattice.datacenters()]
    PROVIDER_CHOICES = ((p.lower(), p) for p in set(providers))

    ip = models.GenericIPAddressField(
        primary_key=True,
        protocol='IPv4',
        verbose_name='IP Address'
    )

    provider = models.CharField(
        choices=PROVIDER_CHOICES,
        max_length=128,
        null=False
    )

    name = models.CharField(max_length=24, verbose_name='Name')
    location = models.CharField(max_length=32, verbose_name='Location')
    usable = models.BooleanField(default=True)

    def __unicode__(self):
        return '{}: {} / {] / {}'.format(self.name, self.provider, self.location, self.ip)
