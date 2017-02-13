import hashlib
from hashids import Hashids
from django.conf import settings

HASHIDS_SALT = getattr(settings, 'SECRET_KEY', '')
HASHIDS_MIN_LENGTH = getattr(settings, 'HASHIDS_MIN_LENGTH', 7)

hashids = Hashids(salt=HASHIDS_SALT, min_length=HASHIDS_MIN_LENGTH)


def _encode(rname, rtype):
    _set_id = ':'.join([str(arg) for arg in (rname, rtype, None)])
    _set_id = int(hashlib.sha256(_set_id.encode('utf-8')).hexdigest()[:16], base=16)

    return hashids.encode(_set_id)


def encode_record(record):
    type_key = 'Type'
    name_key = 'Name'
    set_id = record.get('SetIdentifier', None) or record.get('set_id', None)
    if 'name' in record:
        type_key = 'type'
        name_key = 'name'

    record_type = record[type_key]
    if 'AliasTarget' in record or 'ALIAS' in record[name_key]:
        record_type = record[type_key] + 'ALIAS'

    return set_id or _encode(record[name_key], record_type)
