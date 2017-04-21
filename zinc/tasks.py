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
    aws_zone = zone.r53_zone

    try:
        aws_zone.delete()
    except Exception as e:
        logger.exception(e)
        try:
            self.retry()
        except MaxRetriesExceededError:
            logger.error('Failed to remove zone %s', zone.id)


@shared_task(bind=True, ignore_result=True)
def reconcile_zones(bind=True):
    """
    Periodic task that reconciles everything zone-related (zone deletion, policy record updates)
    """
    redis_client = redis.from_url(settings.LOCK_SERVER_URL)
    lock = redis_client.lock('reconcile_zones', timeout=60)

    if not lock.acquire(blocking=False):
        logger.info('Cannot aquire task lock. Probaly another task is running. Bailing out.')
        return

    try:
        for zone in models.Zone.need_reconciliation():
            try:
                zone.reconcile()
                lock.extend(5)  # extend the lease each time we rebuild a tree
            except:
                logger.exception(
                    "reconcile failed for Zone %s.%s", zone, zone.root
                )
    finally:
        lock.release()


@shared_task(bind=True, ignore_result=True)
def check_clean_zones(bind=True):
    for zone in models.Zone.get_clean_zones():
        zone.r53_zone.check_policy_trees()


@shared_task(bind=True, ignore_result=True)
def reconcile_healthchecks(bind=True):
    route53.HealthCheck.reconcile_for_ips(models.IP.objects.all())


@shared_task(bind=True, ignore_result=True)
def update_ns_propagated(bind=True):
    redis_client = redis.from_url(settings.LOCK_SERVER_URL)

    # make this lock timeout big enough to cover updating about 1000 zones
    # ns_propagated flag and small enough to update the flag in an acceptable
    # time frame. 5 minutes sound good at the moment.

    lock = redis_client.lock('update_ns_propagated', timeout=300)
    if not lock.acquire(blocking=False):
        logger.info('Cannot aquire task lock. Probaly another task is running. Bailing out.')
        return
    try:
        models.Zone.update_ns_propagated(delay=getattr(settings, 'ZINC_NS_UPDATE_DELAY', 0.3))
    except:
        logger.exception("Could not update ns_propagated flag")

    lock.release()
