from django.db import models

from . import IP
from zinc.vendors.boto3 import get_local_aws_regions


class PolicyMember(models.Model):
    ip = models.ForeignKey(IP, on_delete=models.CASCADE)

    AWS_REGIONS = [(region, region) for region in get_local_aws_regions()]
    healthcheck_id = models.IntegerField(editable=False, null=True)
    weight = models.PositiveIntegerField(default=10)
    location = models.CharField(choices=AWS_REGIONS, max_length=20)
