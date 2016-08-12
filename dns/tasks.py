from celery import shared_task
from celery_once import QueueOnce

from zinc.vendors.lattice import lattice


@shared_task(base=QueueOnce, once={'key': [], 'graceful': True})
def lattice_ip_retriever():
    lattice_ips = set()

    for server in lattice.servers():
        lattice_ips |= set(server.ips)

    print(lattice_ips)
