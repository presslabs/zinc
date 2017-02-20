from zinc.vendors import hashids
from zinc import POLICY_ROUTED


def strip_ns_and_soa(records):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return {
        record_hash: dict(record)
        for record_hash, record in records.items()
        if not (record['type'] in ('NS', 'SOA') and record['name'] == '@')
    }


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
