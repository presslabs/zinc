from zinc.vendors import hashids


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
