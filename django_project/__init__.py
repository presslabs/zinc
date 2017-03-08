from .vendors.celery import app as celery_app

POLICY_ROUTED = 'POLICY_ROUTED'

RECORD_TYPES = [
    'A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SOA',
    'SPF', 'SRV', 'NS', POLICY_ROUTED
]

ALLOWED_RECORD_TYPES = set(RECORD_TYPES)
ALLOWED_RECORD_TYPES.remove('SOA')

ZINC_RECORD_TYPES = [(rtype, rtype) for rtype in RECORD_TYPES]

ZINC_RECORD_TYPES_MAP = {i + 1: RECORD_TYPES[i] for i in range(0, len(RECORD_TYPES))}
ZINC_RECORD_TYPES_MAP[0] = POLICY_ROUTED

ZINC_RECORD_TYPES_MAP_REV = {rtype: i for i, rtype in ZINC_RECORD_TYPES_MAP.items()}


def get_record_type(rtype):
    if type(rtype) is int:
        return ZINC_RECORD_TYPES_MAP[rtype]
    else:
        return ZINC_RECORD_TYPES_MAP_REV[rtype]
