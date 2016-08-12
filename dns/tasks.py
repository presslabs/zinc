from datetime import datetime

from celery.utils.log import get_task_logger
from celery import shared_task
from celery_once import QueueOnce

from zinc.vendors.lattice import lattice


logger = get_task_logger(__name__)


@shared_task(base=QueueOnce, once={'key': [], 'graceful': True})
def lattice_ip_retriever():
    logger.info("Start task")
    lattice_ips = set()

    for server in lattice.servers():
        lattice_ips |= set(server.ips)

    logger.info("result {}".format(lattice_ips))
