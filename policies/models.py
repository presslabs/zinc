from django.db import models
from ips.models import IP


class Policy(models.Model):
    name = models.CharField(max_length=255, null=False)
    modified_index = models.PositiveIntegerField(default=0, editable=False)

    ip = models.ManyToManyField(IP)
