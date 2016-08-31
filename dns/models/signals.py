from django.db.models.signals import post_delete
from django.dispatch import receiver

from dns.models.zone import Zone
from dns.tasks import aws_delete_zone


@receiver(post_delete, sender=Zone)
def aws_delete(instance, **kwargs):
    if 'raw' in kwargs and kwargs['raw']:
        return

    aws_delete_zone.delay(instance.route53_id, instance.root)

