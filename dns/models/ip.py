from django.db import models

from dns.validators import validate_hostname


class IP(models.Model):
    ip = models.GenericIPAddressField(
        primary_key=True,
        protocol='IPv4',
        verbose_name='IP Address'
    )
    hostname = models.CharField(max_length=64, validators=[validate_hostname])
    friendly_name = models.TextField(blank=True)

    enabled = models.BooleanField(default=True)

    def __str__(self):
        value = self.friendly_name or self.hostname

        return '{} {}'.format(self.ip, value)

    def __unicode__(self):
        return self.__str__()
