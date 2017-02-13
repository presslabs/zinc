

def strip_ns_and_soa(records):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return {
        record_id: record
        for record_id, record in records.items()
        if not (record['type'] in ('NS', 'SOA') and record['name'] == '@')
    }
