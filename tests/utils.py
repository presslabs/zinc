import json

from django_dynamic_fixture import G

from zinc import models as m
from zinc import route53
from zinc.utils.generators import chunks


def is_ns_or_soa(record):
    if isinstance(record, route53.record.BaseRecord):
        return (record.type in ('NS', 'SOA') and record.name == '@')
    else:
        return (record['type'] in ('NS', 'SOA') and record['name'] == '@')


def strip_ns_and_soa(records):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return [dict(record) for record in records if not is_ns_or_soa(record)]


def hash_test_record(zone):
    return route53.Record(
        name='test',
        type='A',
        zone=zone.r53_zone,
    ).id


def hash_policy_record(policy_record):
    return policy_record.serialize().id


def hash_record_dict(record, zone):
    return route53.Record(zone=zone.r53_zone, **record).id


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
        'fqdn': 'test.%s' % zone.root,
        'ttl': 300,
        'type': 'A',
        'values': ['1.1.1.1'],
        'dirty': False,
        'managed': False,
        'url': 'http://testserver/zones/%s/records/%s' % (zone.id, hash_test_record(zone))
    }


def _split_overlength_value_into_chunks(value):
    # Only TXT records might require splitting their values, so it doesn't matter if we split
    # all record types values in tests

    max_length = 255

    if len(value) >= max_length:
        value = ' '.join('{}'.format(json.dumps(element))
                         for element in chunks(value, max_length))

    return {'Value': value}


def record_data_to_aws(record, zone_root):
    rrs = {
        'Name': '{}.{}'.format(record['name'], zone_root),
        'TTL': record['ttl'],
        'Type': record['type'],
        'ResourceRecords': [_split_overlength_value_into_chunks(value)
                            for value in record['values']],
    }
    if record.get('SetIdentifier', None):
        rrs['SetIdentifier'] = record['SetIdentifier']
    return rrs


def create_ip_with_healthcheck(**kwargs):
    kwargs['healthcheck_id'] = None
    kwargs['healthcheck_caller_reference'] = None
    ip = G(m.IP, **kwargs)
    ip.reconcile_healthcheck()
    ip.refresh_from_db()
    return ip


def record_data_to_response(record, zone, managed=False, dirty=False):
    record_hash = hash_record_dict(record, zone)
    keys = ['name', 'type', 'ttl', 'values']
    return {
        **{key: value for key, value in record.items() if key in keys},
        'fqdn': '{}.{}'.format(record['name'], zone.root),
        'id': record_hash,
        'url': 'http://testserver/zones/%s/records/%s' % (zone.id, record_hash),
        'managed': managed,
        'dirty': dirty
    }


def record_to_response(record, zone, managed=False, dirty=False):
    record_hash = record.id
    keys = ['name', 'type', 'ttl', 'values']
    return {
        **{key: getattr(record, key) for key in keys},
        'fqdn': '{}.{}'.format(record.name, zone.root),
        'id': record_hash,
        'url': 'http://testserver/zones/%s/records/%s' % (zone.id, record_hash),
        'managed': managed,
        'dirty': dirty
    }


def get_record_from_base(record, *a, **kwa):
    if isinstance(record, route53.Record):
        return record_to_response(record, *a, **kwa)
    else:
        return record_data_to_response(record, *a, **kwa)


def meld(got, expected):
    if got == expected:
        return
    import inspect
    call_frame = inspect.getouterframes(inspect.currentframe(), 2)
    test_name = call_frame[1][3]
    from pprint import pformat
    import os
    from os import path
    os.makedirs(test_name, exist_ok=True)
    got_fn = path.join(test_name, 'got')
    expected_fn = path.join(test_name, 'expected')
    with open(got_fn, 'w') as got_f, open(expected_fn, 'w') as expected_f:
        got_f.write(pformat(got))
        expected_f.write(pformat(expected))
    import subprocess
    subprocess.run(['meld', got_fn, expected_fn])
