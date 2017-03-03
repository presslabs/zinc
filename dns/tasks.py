from celery.utils.log import get_task_logger
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from dns.utils import route53
from dns import models


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


@shared_task(bind=True, ignore_result=True, default_retry_delay=60)
def reconcile_zones(self):
    """
    Periodic task to delete zones that are soft deleted but still exist in the db,
    or zones that have been created in the db but don't exist in AWS.
    """
    route53.Zone.reconcile_multiple(models.Zone.objects.filter(deleted=True, route53_id=None))


@shared_task(bind=True, ignore_result=True, default_retry_delay=60)
def reconcile_policy_records(bind=True):
    """Periodic task to reconcile dirty policy records"""
    for policy in models.PolicyRecord.objects.filter(dirty=True):
        try:
            policy.apply_record()
        except:
            logger.exception(
                "apply_record failed for PolicyRecord %s.%s", policy.name, policy.zone.root
            )


@shared_task(bind=True, ignore_result=True, default_retry_delay=60)
def reconcile_healthchecks(bind=True):
    route53.Healthcheck.reconcile_for_ips(models.IP.objects.all())
