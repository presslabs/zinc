import redis

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger
from django.conf import settings

from zinc import models, route53

logger = get_task_logger(__name__)


@shared_task(bind=True, ignore_result=True, default_retry_delay=60)
def aws_delete_zone(self, pk):
    zone = models.Zone.objects.get(pk=pk)
    assert zone.deleted
    aws_zone = zone.route53_zone

    try:
        aws_zone.delete()
    except Exception as e:
        logger.exception(e)
        try:
            self.retry()
        except MaxRetriesExceededError:
            logger.error('Failed to remove zone %s', zone.id)


@shared_task(bind=True, ignore_result=True)
def reconcile_zones(self):
    """
    Periodic task to delete zones that are soft deleted but still exist in the db,
    or zones that have been created in the db but don't exist in AWS.
    """
    route53.Zone.reconcile_multiple(models.Zone.objects.filter(deleted=True, route53_id=None))


@shared_task(bind=True, ignore_result=True)
def reconcile_policy_records(bind=True):
    """Periodic task to reconcile dirty policy records"""
    redis_client = redis.from_url(settings.LOCK_SERVER_URL)
    lock = redis_client.lock('reconcile_policy_records', timeout=60)

    if not lock.acquire(blocking=False):
        logger.info('Cannot aquire task lock. Probaly another task is running. Bailing out.')
        return

    for zone in models.Zone.objects.filter(policy_records__dirty=True).distinct():
        try:
            zone.build_tree()
            lock.extend(5)  # extend the lease each time we rebuild a tree
        except:
            logger.exception(
                "apply_record failed for Zone %s.%s", zone, zone.root
            )

    lock.release()


@shared_task(bind=True, ignore_result=True)
def reconcile_healthchecks(bind=True):
    route53.HealthCheck.reconcile_for_ips(models.IP.objects.all())


@shared_task(bind=True, ignore_result=True)
def update_ns_propagated(bind=True):
    models.Zone.update_ns_propagated(delay=getattr(settings, 'ZINC_NS_UPDATE_DELAY', 0.3))
