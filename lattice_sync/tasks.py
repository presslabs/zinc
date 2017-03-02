from celery.utils.log import get_task_logger
from celery import shared_task
from django.conf import settings

from lattice_sync import sync

logger = get_task_logger(__name__)


@shared_task(ignore_result=True, default_retry_delay=60)
def lattice_sync():
    lattice = sync.lattice_factory(
        settings.LATTICE_URL, settings.LATTICE_USER, settings.LATTICE_PASSWORD)
    sync.sync(lattice)
