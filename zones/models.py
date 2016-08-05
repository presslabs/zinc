from django.db import models
from django.core.validators import MinValueValidator


class Zone(models.Model):
    # TODO validate root here trailing dot and stuff
    root = models.CharField(max_length=255, unique=True)
    aws_id = models.IntegerField(unique=True)

    def __unicode__(self):
        return self.root


class Record(models.Model):
    RECORD_TYPES = [(type, type) for type in ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SPF', 'SRV', 'NS', 'SOA']]

    name = models.CharField(max_length=64, null=False)
    type = models.CharField(choices=RECORD_TYPES, null=False, max_length=4, default=RECORD_TYPES[0][0])
    value = models.TextField(null=False)
    ttl = models.IntegerField(validators=[MinValueValidator(300)], default=3600)
    managed = models.BooleanField(default=False)

    zone = models.ForeignKey(Zone, on_delete=models.CASCADE)

    # TODO think about value validation
