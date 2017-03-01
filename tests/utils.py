from zinc.vendors import hashids
from zinc import POLICY_ROUTED
from dns import models as m


def strip_ns_and_soa(records):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return [
        dict(record) for record in records
        if not (record['type'] in ('NS', 'SOA') and record['name'] == '@')
    ]


def hash_test_record(zone):
    return hashids.encode_record({
        'name': 'test',
        'type': 'A'
    }, zone.route53_zone.id)


def hash_policy_record(policy_record):
    return hashids.encode_record({
        'name': policy_record.name,
        'type': POLICY_ROUTED,
    }, policy_record.zone.route53_zone.id)


def hash_record(record, zone):
    return hashids.encode_record(record, zone.route53_zone.id)


def aws_sort_key(record):
    return (record['Name'], record['Type'], record.get('SetIdentifier', None))


def aws_strip_ns_and_soa(records, zone_root):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return sorted([
        record for record in records['ResourceRecordSets']
        if not(record['Type'] == 'SOA' or (record['Type'] == 'NS' and record['Name'] == zone_root))
    ], key=aws_sort_key)


def get_test_record(zone):
    return {
        'id': hash_test_record(zone),
        'name': 'test',
        'ttl': 300,
        'type': 'A',
        'values': ['1.1.1.1'],
        'dirty': False,
        'managed': False,
        'url': 'http://testserver/zones/%s/records/%s' % (zone.id, hash_test_record(zone))
    }


def record_to_aws(record, zone_root):
    rrs = {
        'Name': '{}.{}'.format(record['name'], zone_root),
        'TTL': record['ttl'],
        'Type': record['type'],
        'ResourceRecords': [{'Value': value} for value in record['values']],
    }
    if record.get('SetIdentifier', None):
        rrs['SetIdentifier'] = record['SetIdentifier']
    return rrs


def create_ip_with_healthcheck(ip='1.2.3.4'):
    ip = m.IP.objects.create(
        ip=ip,
        hostname='fe01-mordor.presslabs.net.',
    )
    ip.reconcile_healthcheck()
    ip.refresh_from_db()
    return ip

def get_record_from_base(record, zone, managed=False, dirty=False):
    record_hash = hash_record(record, zone)
    KEYS = ['name', 'type', 'ttl', 'values']
    return {
        **{key: value for key, value in record.items() if key in KEYS},
        'id': record_hash,
        'url': 'http://testserver/zones/%s/records/%s' % (zone.id, record_hash),
        'managed': managed,
        'dirty': dirty
    }
