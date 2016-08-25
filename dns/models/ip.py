from django.db import models

from zinc.vendors.lattice import lattice


_providers = [d['provider'].split('.')[2] for d in lattice.datacenters()]
_provider_choices = ((p.lower(), p) for p in set(_providers))
_hostnames = [s['hostname'] for s in lattice.servers()]
_hostname_choices = ((h, h) for h in _hostnames)


# TODO shouldn't be editable in admin, only listable
class IP(models.Model):
    ip = models.GenericIPAddressField(
        primary_key=True,
        protocol='IPv4',
        verbose_name='IP Address'
    )
    provider = models.CharField(
        choices=_provider_choices,
        max_length=128,
        null=False
    )
    name = models.CharField(max_length=24, verbose_name='Name')

    location = models.CharField(
        choices=_hostname_choices,
        max_length=32,
        verbose_name='Location'
    )
    usable = models.BooleanField(default=True)

    def __unicode__(self):
        return '{}: {} / {] / {}'.format(self.name, self.provider, self.location, self.ip)
