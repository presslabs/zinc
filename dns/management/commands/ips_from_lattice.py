import logging

from urllib.parse import urlparse
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from django.core.management.base import BaseCommand

from zipa import lattice

from dns.models import IP
from dns.utils.generic import list_overlap

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Imports IPs from a lattice server'

    def add_arguments(self, parser):
        parser.add_argument('--url', default='')
        parser.add_argument('--user', default='')
        parser.add_argument('--password', default='')
        parser.add_argument('--roles', nargs='*')

    def handle(self, *args, **options):
        lattice = lattice_vendor(options['url'],
                                 options['user'],
                                 options['password'])

        try:
            servers = [server for server in lattice.servers() if
                       list_overlap(server['roles'],
                                    options['roles']) and
                       server['state'] not in ['unconfigured',
                                               'decommissioned']]
            locations = {d['id']: d['location'] for d in
                         lattice.datacenters()}
        except HTTPError as e:
            logger.exception(e)
            return

        lattice_ips = set()
        for server in servers:
            for ip in server.ips:
                enabled = server['state'] == 'configured'

                datacenter_id = int(
                    server['datacenter_url'].split('?')[0].split('/')[-1])
                location = locations.get(datacenter_id, 'fake_location')

                friendly_name = '{} {} {}'.format(server['hostname'],
                                                  server['datacenter_name'],
                                                  location)
                cron_ip = IP(ip=ip['ip'], hostname=server['hostname'],
                             friendly_name=friendly_name, enabled=enabled)

                try:
                    cron_ip.save()
                    lattice_ips.add(ip['ip'])
                except Exception as e:
                    logger.info('{} - {}'.format(ip, e))

        ips_to_remove = set(
            IP.objects.values_list('ip', flat=True)) - lattice_ips
        IP.objects.filter(ip__in=ips_to_remove).delete()


def lattice_vendor(url, user, password):
    parts = urlparse(url)

    if url.startswith('http://'):
        lattice.config.secure = False
        lattice.config.verify = False

    lattice.config.host = parts.netloc
    lattice.config.prefix = parts.path
    lattice.config.append_slash = True
    lattice.config.auth = HTTPBasicAuth(user, password)

    return lattice
