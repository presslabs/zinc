from urllib.parse import urlparse
from logging import getLogger

from django.conf import settings
from django.db import transaction
from requests.auth import HTTPBasicAuth
from zipa import lattice  # pylint: disable=no-name-in-module

from zinc import models
from zinc.utils.validation import is_ipv6


logger = getLogger('zinc.' + __name__)


def lattice_factory(url, user, password):
    parts = urlparse(url)

    if url.startswith('http://'):
        lattice.config.secure = False
        lattice.config.verify = False

    lattice.config.host = parts.netloc
    lattice.config.prefix = parts.path
    lattice.config.auth = HTTPBasicAuth(user, password)
    return lattice


@transaction.atomic
def handle_ip(ip_addr, server, locations):
    # ignore ipv6 addresses for now
    if is_ipv6(ip_addr):
        return

    enabled = server['state'] == 'configured'
    datacenter_id = int(
        server['datacenter_url'].split('?')[0].split('/')[-1])
    location = locations.get(datacenter_id, 'fake_location')

    friendly_name = '{} {}'.format(server['hostname'].split('.')[0],
                                   location)
    ip = models.IP.objects.filter(
        ip=ip_addr,
    ).first()
    changed = False
    if ip is None:  # new record
        ip = models.IP(ip=ip_addr)
        ip.reconcile_healthcheck()
        changed = True
    elif ip.enabled != enabled:
        ip.enabled = enabled
        ip.mark_policy_records_dirty()
        changed = True
    if ip.hostname != server['hostname']:
        ip.hostname = server['hostname']
        changed = True
    if ip.friendly_name != friendly_name:
        ip.friendly_name = friendly_name
        changed = True
    if changed:
        ip.save()
    return ip.pk


def sync(lattice_client):
    roles = set(settings.LATTICE_ROLES)
    env = settings.LATTICE_ENV.lower()
    servers = [
        server for server in lattice.servers
        if (set(server['roles']).intersection(roles) and
            server['environment'].lower() == env and
            server['state'].lower() not in ('unconfigured', 'decommissioned'))
    ]
    locations = {d['id']: d['location'] for d in lattice.datacenters}

    lattice_ip_pks = set()
    for server in servers:
        for ip in server.ips:
            try:
                ip_pk = handle_ip(ip['ip'], server, locations)
            except:
                logger.exception("Error while handling ip: %s", ip['ip'])
            else:
                if ip_pk is not None:
                    lattice_ip_pks.add(ip_pk)
    if not lattice_ip_pks:
        raise AssertionError("Refusing to delete all IPs!")
    ips_to_remove = set(
        models.IP.objects.values_list('pk', flat=True)) - lattice_ip_pks
    for ip in models.IP.objects.filter(pk__in=ips_to_remove):
        ip.soft_delete()
