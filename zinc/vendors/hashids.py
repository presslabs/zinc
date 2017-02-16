import hashlib
from hashids import Hashids
from django.conf import settings

from zinc import get_record_type

HASHIDS_SALT = getattr(settings, 'SECRET_KEY', '')
HASHIDS_MIN_LENGTH = getattr(settings, 'HASHIDS_MIN_LENGTH', 7)
HASHIDS_ALPHABET = getattr(settings, 'HASHIDS_ALPHABET',
                           'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXY1234567890')

hashids = Hashids(salt=HASHIDS_SALT,
                  alphabet=HASHIDS_ALPHABET)


def _encode(*args):
    _set_id = ':'.join([str(arg) for arg in args])
    _set_id = int(hashlib.sha256(_set_id.encode('utf-8')).hexdigest()[:16], base=16)

    return hashids.encode(_set_id)


def encode_record(record, zone_id=''):
    zone_hash = _encode(zone_id)
    type_key = 'Type'
    name_key = 'Name'
    set_id = record.get('SetIdentifier', None)
    if 'name' in record:
        type_key = 'type'
        name_key = 'name'

    record_hash = _encode(record[name_key], record[type_key], set_id)
    record_type = get_record_type(record[type_key])

    return 'Z{zone}Z{type}Z{id}'.format(zone=zone_hash, type=record_type, id=record_hash)
