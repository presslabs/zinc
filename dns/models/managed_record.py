from django.core.validators import MinValueValidator
from django.db import models


class ManagedRecord(models.Model):
    name = models.CharField(max_length=255)
    record_type = models.CharField(
        default='POLICY_ROUTED',
        max_length=13,
        editable=False
    )
    value = models.TextField()
    ttl = models.IntegerField(validators=[MinValueValidator(300)])
    dirty = models.BooleanField(default=True, editable=False)
