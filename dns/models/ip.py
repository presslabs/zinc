from django.core.validators import validate_ipv46_address
from django.db import models


class IP(models.Model):
    # TODO FILL REGIONS HERE
    AWS_REGIONS = [('us', 'US')]

    ip = models.CharField(
        max_length=40,
        verbose_name='IP Address',
        validators=[validate_ipv46_address],
        primary_key=True
    )
    server_name = models.CharField(max_length=255)

    healthcheck_id = models.IntegerField(editable=False, null=True)
    weight = models.PositiveIntegerField(default=10)
    location = models.CharField(choices=AWS_REGIONS, max_length=10)

    def __unicode__(self):
        return '{}: {} - {}'.format(self.ip, self.location, self.server_name)
