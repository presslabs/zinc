from django.db import models


class Record(models.Model):
    name = models.CharField(max_length=255)
    rtype = models.CharField(max_length=10)
    value = models.CharField(default='')
    ttl = models.PositiveIntegerField(default=300)


class Zone(models.Model):
    zone_id = models.CharField(primary_key=True)
    root = models.CharField(
            max_length=255,
            unique=True
    )
    records = models.ForeignKey(Record)

    def __str__(self):
        return self.root
