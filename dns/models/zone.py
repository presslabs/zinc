from django.db import models
from django.db.models.signals import pre_save

from ..validators import validate_root_domain


class Zone(models.Model):
    root = models.CharField(
        max_length=255,
        unique=True,
        validators=[validate_root_domain]
    )
    aws_id = models.IntegerField(editable=False)
    dirty = models.BooleanField(default=False, editable=False)

    records = models.TextField(default='[]')

    def __unicode__(self):
        return self.root


def mark_dirty(sender, instance, *args, **kwargs):
    instance.dirty = True


# TODO make this an celery task
def create_aws_zone(sender, instance, *args, **kwargs):
    # TODO make this happen
    print('triggered')
    instance.aws_id = 12345


pre_save.connect(mark_dirty, sender=Zone)
pre_save.connect(create_aws_zone, sender=Zone)
