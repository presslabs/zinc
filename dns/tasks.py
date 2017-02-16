from celery.utils.log import get_task_logger
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from dns.utils import route53

logger = get_task_logger(__name__)


@shared_task(bind=True, ignore_result=True, default_retry_delay=60)
def aws_delete_zone(self, pk):
    assert False
    zone = models.Zone.objects.get(pk=pk)
    aws_zone = route53.Zone(id=zone.route53_id, root=zone.root)

    try:
        aws_zone.delete()
        zone.delete()
    except Exception as e:
        logger.exception(e)
        try:
            self.retry()
        except MaxRetriesExceededError:
            logger.error('Failed to remove zone {}'.format(zone_id))
