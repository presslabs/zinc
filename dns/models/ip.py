from django.db import models

from dns.validators import validate_hostname
from zinc.vendors.lattice import lattice


class IP(models.Model):
    ip = models.GenericIPAddressField(
        primary_key=True,
        protocol='IPv4',
        verbose_name='IP Address'
    )

    hostname = models.CharField(max_length=64, validators=[validate_hostname])
    friendly_name = models.TextField(blank=True)

    enabled = models.BooleanField(default=True)

    def __unicode__(self):
        return self.friendly_name or '{} - {}'.format(self.hostname, self.ip)
