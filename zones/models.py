from django.db import models


class Zone(models.Model):
    root = models.CharField(max_length=255)
    aws_id = models.IntegerField(unique=True)

    def __unicode__(self):
        return self.root

