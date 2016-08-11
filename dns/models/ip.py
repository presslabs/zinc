from django.db import models

from ..utils import get_regions


class IP(models.Model):
    AWS_REGIONS = get_regions()

    ip = models.GenericIPAddressField(
        primary_key=True,
        protocol='IPv4',
        verbose_name='IP Address'
    )
    server_name = models.CharField(max_length=255)
    healthcheck_id = models.IntegerField(editable=False, null=True)
    weight = models.PositiveIntegerField(default=10)
    location = models.CharField(choices=AWS_REGIONS, max_length=10)

    def __unicode__(self):
        return '{}: {} - {}'.format(self.ip, self.location, self.server_name)
