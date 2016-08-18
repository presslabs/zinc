from requests.exceptions import HTTPError

from celery.utils.log import get_task_logger
from celery import shared_task
from celery_once import QueueOnce

from django.conf import settings

from dns.models.ip import IP
from dns.utils import list_overlap
from zinc.vendors.lattice import lattice

logger = get_task_logger(__name__)


@shared_task(base=QueueOnce, default_retry_delay=30, max_retries=3, soft_time_limit=600,
             once={'key': [], 'graceful': True})
def lattice_ip_retriever():
    try:
        servers = [server for server in lattice.servers() if
                   list_overlap(server['roles'], settings.LATTICE_ROLES) and server['state'] not in ['unconfigured',
                                                                                                     'decommissioned']]
    except HTTPError:
        servers = []

    lattice_ips = set()
    for server in servers:
        for ip in server.ips:
            # TODO retrieve location
            usable = server['state'] == 'configured'
            cron_ip = IP(ip=ip['ip'], provider=server['datacenter_name'], name=server['hostname'], location='TEST',
                         usable=usable)

            try:
                cron_ip.save()
                lattice_ips.add(ip['ip'])
            except Exception as e:
                logger.info('{} - {}'.format(ip, e))

    ips_to_remove = set(IP.objects.values_list('ip', flat=True)) - lattice_ips
    IP.objects.filter(ip__in=ips_to_remove).delete()
