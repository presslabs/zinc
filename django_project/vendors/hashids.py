import hashlib
from hashids import Hashids
from django.conf import settings

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
