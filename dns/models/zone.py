from django.db import models
from django.db.models.signals import pre_save

from ..validators import validate_domain


class Zone(models.Model):
    root = models.CharField(
        max_length=255,
        validators=[validate_domain]
    )
    route53_id = models.IntegerField(editable=False)

    def __unicode__(self):
        return self.name


def mark_dirty(sender, instance, *args, **kwargs):
    instance.dirty = True


# TODO make this an celery task
def create_aws_zone(sender, instance, *args, **kwargs):
    # TODO make this happen
    print('triggered')
    instance.route53_id = 12345


pre_save.connect(mark_dirty, sender=Zone)
pre_save.connect(create_aws_zone, sender=Zone)
