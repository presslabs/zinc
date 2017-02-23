from urllib.parse import urlparse
from requests.auth import HTTPBasicAuth

from django.conf import settings
from zipa import lattice  # pylint: disable=no-name-in-module

from dns import models


def lattice_factory(url, user, password):
    parts = urlparse(url)

    if url.startswith('http://'):
        lattice.config.secure = False
        lattice.config.verify = False

    lattice.config.host = parts.netloc
    lattice.config.prefix = parts.path
    lattice.config.append_slash = True
    lattice.config.auth = HTTPBasicAuth(user, password)

    return lattice


def sync(lattice_client):
    roles = set(settings.LATTICE_ROLES)
    servers = [server for server in lattice.servers()
               if (set(server['roles']).intersection(roles) and
                   server['state'] not in ('unconfigured', 'decommissioned'))]
    locations = {d['id']: d['location'] for d in lattice.datacenters()}

    lattice_ip_pks = set()
    for server in servers:
        for ip in server.ips:
            enabled = server['state'] == 'configured'

            datacenter_id = int(
                server['datacenter_url'].split('?')[0].split('/')[-1])
            location = locations.get(datacenter_id, 'fake_location')

            friendly_name = '{} {} {}'.format(server['hostname'],
                                              server['datacenter_name'],
                                              location)
            cron_ip = models.IP(ip=ip['ip'], hostname=server['hostname'],
                                friendly_name=friendly_name, enabled=enabled)
            cron_ip.save()
            lattice_ip_pks.add(cron_ip.pk)

    ips_to_remove = set(
        models.IP.objects.values_list('pk', flat=True)) - lattice_ip_pks
    models.IP.objects.filter(pk__in=ips_to_remove).delete()
