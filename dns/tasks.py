from datetime import datetime

from celery.utils.log import get_task_logger
from celery import shared_task
from celery_once import QueueOnce

from zinc.vendors.lattice import lattice

logger = get_task_logger(__name__)


@shared_task(base=QueueOnce, default_retry_delay=30, max_retries=3, soft_time_limit=600,
             once={'key': [], 'graceful': True})
def lattice_ip_retriever():
    logger.info("Start task")
    lattice_ips = set()

    for server in lattice.servers():
        lattice_ips |= set(server.ips)

    logger.info("result {}".format(lattice_ips))


@shared_task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))


@shared_task(base=QueueOnce, once={'key': [], 'graceful': True})
def slow_task():
    sleep(30)
    return "Done!"
