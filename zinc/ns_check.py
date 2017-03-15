from django.conf import settings

from dns.resolver import Resolver
from dns.exception import DNSException


class CouldNotResolve(Exception):
    pass


def get_resolver():
    resolver = Resolver()
    resolver.nameservers = settings.ZINC_NS_CHECK_RESOLVERS
    return resolver


def is_ns_propagated(zone, resolver=None):
    if not zone.route53_zone.exists:
        return False
    if resolver is None:
        resolver = get_resolver()
    r53_name_servers = set(zone.route53_zone.ns['values'])
    try:
        name_servers = set([str(ns) for ns in resolver.query(zone.root, 'NS')])
    except DNSException as e:
        raise CouldNotResolve(e)
    return r53_name_servers == name_servers
