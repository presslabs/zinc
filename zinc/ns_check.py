import json
import time

from django.conf import settings

from dns.resolver import Resolver
from dns.exception import DNSException


class CouldNotResolve(Exception):
    pass


def get_resolver():
    resolver = Resolver()
    resolver.nameservers = settings.ZINC_NS_CHECK_RESOLVERS
    return resolver


def is_ns_propagated(zone, resolver=None, delay=0):
    if not zone.r53_zone.exists:
        return False
    if resolver is None:
        resolver = get_resolver()
    try:
        name_servers = sorted([str(ns) for ns in resolver.query(zone.root, 'NS')])
    except DNSException as e:
        raise CouldNotResolve(e)
    if zone.cached_ns_records:
        r53_name_servers = json.loads(zone.cached_ns_records)
        if delay:
            time.sleep(delay)
        if r53_name_servers == name_servers:
            return True
    # in case the nameservers don't match we update the cached_ns_records and
    # compare again
    r53_name_servers = sorted(zone.r53_zone.ns.values)
    zone.cached_ns_records = json.dumps(r53_name_servers)
    zone.save(update_fields=['cached_ns_records'])
    return r53_name_servers == name_servers
