from django.db import models


class Zone(models.Model):
    # TODO validate root here trailing dot and stuff
    root = models.CharField(max_length=255, unique=True)
    aws_id = models.IntegerField(unique=True, editable=False)
    dirty = models.BooleanField(default=False)

    records = models.TextField(default='[]')

    def __unicode__(self):
        return self.root
