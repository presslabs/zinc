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

RECORD_PREFIX = '_zn'

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
        self.alias_target = alias_target
        assert alias_target is None or ttl is None
        self.ttl = ttl
        self._values = values
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
        return "<Record id={} {}:{} {}>".format(self.id, self.type, self.name, self.values)

    @property
    def values(self):
        if self.is_alias:
            if 'DNSName' in self.alias_target:
                return ['ALIAS {}'.format(self.alias_target['DNSName'])]
        else:
            return self._values

    @values.setter
    def values(self, value):
        assert not self.is_alias
        self._values = value

    @staticmethod
    def _strip_root(name, root):
        return '@' if name == root else name.replace('.' + root, '')

    @staticmethod
    def _add_root(name, root):
        return root if name == '@' else '{}.{}'.format(name, root)

    @classmethod
    def from_aws_record(cls, record, zone):
        # Determine if a R53 DNS record is of type ALIAS
        def is_alias_record(record):
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
                       root_ns_soa(record, zone.root) or (is_alias_record(record)))

        new.ttl = record.get('TTL')
        if is_alias_record(record):
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

    def to_aws(self):
        encoded_record = {
            'Name': self._add_root(self.name, self.zone_root),
            'Type': self.type,
        }
        if not self.is_alias:
            if self.type == 'TXT':
                # Encode json escape.
                encoded_record['ResourceRecords'] = [{'Value': json.dumps(value)}
                                                     for value in self.values]
            else:
                encoded_record['ResourceRecords'] = [{'Value': value} for value in self.values]
        else:
            encoded_record['AliasTarget'] = {
                'DNSName': self.alias_target['DNSName'],
                'EvaluateTargetHealth': self.alias_target['EvaluateTargetHealth'],
                'HostedZoneId': self.alias_target['HostedZoneId'],
            }
        if self.ttl is not None:
            encoded_record['TTL'] = self.ttl

        for attr_name in ['Weight', 'Region', 'SetIdentifier',
                          'HealthCheckId', 'TrafficPolicyInstanceId']:
            value = getattr(self, self._r53_to_obj[attr_name])
            if value is not None:
                encoded_record[attr_name] = value

        return encoded_record

    @property
    def is_alias(self):
        return self.alias_target is not None

    @property
    def is_policy_record(self):
        # assert self.type != POLICY_ROUTED
        return self.type == POLICY_ROUTED

    @property
    def is_hidden(self):
        return self.name.startswith(RECORD_PREFIX)  # or (
            # self.is_alias and self.alias_target['DNSName'].startswith(RECORD_PREFIX))

    def is_member_of(self, policy):
        return self.name.startswith('{}_{}'.format(RECORD_PREFIX, policy.name))


class PolicyRecord(Record):
    def __init__(self, policy_record, zone, type=POLICY_ROUTED):
        self.policy_record = policy_record
        self.policy = policy_record.policy
        self.zone = zone
        super().__init__(
            name=self.policy_record.name,
            zone=zone,
            alias_target={
                'HostedZoneId': zone.id,
                'DNSName': '{}_{}.{}'.format(RECORD_PREFIX, self.policy.name, zone.root),
                'EvaluateTargetHealth': False
            },
            type=POLICY_ROUTED,
            values=[str(self.policy.id)],
            deleted=self.policy_record.deleted,
        )

    def reconcile(self):
        # create the top level alias
        if self.deleted:
            # if the zone is marked as deleted don't try to build the tree.
            self.zone.add_records([self])
            self.zone.commit()
            self.policy_record.delete()
        else:
            self.zone.add_records([self])
            self.policy_record.dirty = False  # mark as clean
            self.zone.commit()
            self.policy_record.save()

    @property
    def is_policy_record(self):
        return True

    def _top_level_record(self):
        return Record(
            name=self.name,
            type='A',
            alias_target={
                'HostedZoneId': self.zone.id,
                'DNSName': '{}_{}.{}'.format(RECORD_PREFIX, self.policy.name, self.zone.root),
                'EvaluateTargetHealth': False
            },
            zone=self.zone,
        )

    def to_aws(self):
        return self._top_level_record().to_aws()

    @property
    def id(self):
        return self._top_level_record().id

# class CachingFactory:
#     def __init__(self, klass, key=('name', 'type')):
#         self._registry = {}
#         self._klass = klass

#     def get(self, *constructor_args, cache_key=None):
#         if cache_key is None:
#             cache_key = constructor_args
#         obj = self._registry.get(cache_key)
#         if obj is None:
#             obj = self._klass(*constructor_args)
#             self._registry[cache_key] = obj
#         return obj

#     def __call__(self, key, constructor_args=None):
#         return self.get(key, constructor_args)
