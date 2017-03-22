import json
import hashlib

from hashids import Hashids
from django.conf import settings

HASHIDS_SALT = getattr(settings, 'SECRET_KEY', '')
HASHIDS_MIN_LENGTH = getattr(settings, 'HASHIDS_MIN_LENGTH', 7)
HASHIDS_ALPHABET = getattr(settings, 'HASHIDS_ALPHABET',
                           'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXY1234567890')
hashids = Hashids(salt=HASHIDS_SALT,
                  alphabet=HASHIDS_ALPHABET)


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


def _encode(*args):
    _set_id = ':'.join([str(arg) for arg in args])
    _set_id = int(hashlib.sha256(_set_id.encode('utf-8')).hexdigest()[:16], base=16)
    return hashids.encode(_set_id)


class Record:
    _obj_to_r53 = dict([
        ('name', 'Name'),
        ('type', 'Type'),
        ('managed', 'Managed'),
        ('ttl', 'ttl'),
        ('alias_target', 'AliasTarget'),
        ('values', 'Values'),
        ('weight', 'Weight'),
        ('region', 'Region'),
        ('set_identifier', 'SetIdentifier'),
        ('health_check_id', 'HealthCheckId'),
        ('traffic_policy_instance_id', 'TrafficPolicyInstanceId'),
    ])
    _r53_to_obj = {v: k for k, v in _obj_to_r53.items()}

    def __init__(self, name=None, type=None, alias_target=None, deleted=False, dirty=False,
                 health_check_id=None, managed=False, region=None, set_identifier=None,
                 traffic_policy_instance_id=None, ttl=None, values=None, weight=None,
                 zone=None):
        self.name = name
        self.type = type
        self.ttl = ttl
        self.alias_target = alias_target
        self.values = values
        self.weight = weight
        self.region = region
        self.set_identifier = set_identifier
        self.health_check_id = health_check_id
        self.traffic_policy_instance_id = traffic_policy_instance_id
        self.zone_id = zone.id
        self.zone_root = zone.root
        assert self.zone_id is not None
        assert self.zone_root is not None
        self.deleted = deleted
        self.dirty = dirty
        self.managed = managed

    def __repr__(self):
        return "<Record id={} {}:{}>".format(self.id, self.type, self.name)

    @staticmethod
    def _strip_root(name, root):
        return '@' if name == root else name.replace('.' + root, '')

    @staticmethod
    def _add_root(name, root):
        return root if name == '@' else '{}.{}'.format(name, root)

    @classmethod
    def from_aws_record(cls, record, zone):
        # Determine if a R53 DNS record is of type ALIAS
        def alias_record(record):
            return 'AliasTarget' in record.keys()

        # Determine if a record is the NS or SOA record of the root domain
        def root_ns_soa(record, root):
            return record['Name'] == root and record['Type'] in ['NS', 'SOA']

        kwargs = {}
        for attr_name in ['weight', 'region', 'set_identifier', 'health_check_id',
                          'traffic_policy_instance_id']:
            kwargs[attr_name] = record.get(cls._obj_to_r53[attr_name], None)

        new = cls(zone=zone, **kwargs)
        new.name = cls._strip_root(record['Name'], zone.root)
        new.type = record['Type']
        new.managed = ((record.get('SetIdentifier', False)) or
                       root_ns_soa(record, zone.root) or (alias_record(record)))

        new.ttl = record.get('TTL')
        if alias_record(record):
            new.alias_target = {
                'DNSName': record['AliasTarget']['DNSName'],
                'EvaluateTargetHealth': record['AliasTarget']['EvaluateTargetHealth'],
                'HostedZoneId': record['AliasTarget']['HostedZoneId']
            }
        elif record['Type'] == 'TXT':
            # Decode json escaped strings
            new.values = [json.loads('[%s]' % value['Value'])[0]
                          for value in record.get('ResourceRecords', [])]
        else:
            new.values = [value['Value'] for value in
                          record.get('ResourceRecords', [])]
        return new

    @property
    def id(self):
        zone_hash = _encode(self.zone_id)
        record_hash = _encode(self.name, self.type, self.set_identifier)
        return 'Z{zone}Z{type}Z{id}'.format(
            zone=zone_hash, type=get_record_type(self.type), id=record_hash)

    def encode(self):
        encoded_record = {
            'Name': self._add_root(self.name, self.zone_root),
            'Type': self.type,
        }
        if self.values is not None:
            if self.type == 'TXT':
                # Encode json escape.
                encoded_record['ResourceRecords'] = [{'Value': json.dumps(value)}
                                                     for value in self.values]
            else:
                encoded_record['ResourceRecords'] = [{'Value': value} for value in self.values]

        if self.ttl is not None:
            encoded_record['TTL'] = self.ttl

        if self.alias_target is not None:
            encoded_record['AliasTarget'] = {
                'DNSName': self.alias_target['DNSName'],
                'EvaluateTargetHealth': self.alias_target['EvaluateTargetHealth'],
                'HostedZoneId': self.alias_target['HostedZoneId'],
            }

        for attr_name in ['Weight', 'Region', 'SetIdentifier',
                          'HealthCheckId', 'TrafficPolicyInstanceId']:
            value = getattr(self, self._r53_to_obj[attr_name])
            if value is not None:
                encoded_record[attr_name] = value

        return encoded_record
