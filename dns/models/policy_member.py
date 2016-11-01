from django.conf import settings
from django.db import models
from hashid_field import HashidField

from dns.models import IP
from dns.utils.route53 import get_local_aws_regions


class PolicyMember(models.Model):
    AWS_REGIONS = [(region, region) for region in get_local_aws_regions()]

    id = HashidField(
            editable=False,
            min_length=getattr(settings, 'HASHIDS_MIN_LENGTH', 7),
            primary_key=True
         )
    location = models.CharField(choices=AWS_REGIONS, max_length=20)
    ip = models.ForeignKey(IP, on_delete=models.CASCADE)
    healthcheck_id = models.IntegerField(editable=False, null=True)
    weight = models.PositiveIntegerField(default=10)

    def __str__(self):
        return '{} {} {}'.format(self.ip, self.location, self.weight)

    def __unicode__(self):
        return self.__str__()
