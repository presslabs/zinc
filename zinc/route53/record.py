import json
import hashlib

from hashids import Hashids
from django.conf import settings
from django.core.exceptions import SuspiciousOperation, ValidationError

from zinc import models, route53
from zinc.utils import memoized_property


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


class BaseRecord:
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

    def __init__(self, name=None, alias_target=None, created=False, deleted=False, dirty=False,
                 health_check_id=None, managed=False, region=None, set_identifier=None,
                 traffic_policy_instance_id=None, ttl=None, values=None, weight=None,
                 zone=None):
        self.name = name
        self.alias_target = alias_target
        self.created = created
        assert alias_target is None or ttl is None
        self.ttl = ttl
        self._values = values
        self.weight = weight
        self.region = region
        self.set_identifier = set_identifier
        self.health_check_id = health_check_id
        self.traffic_policy_instance_id = traffic_policy_instance_id
        self.zone = zone
        self.zone_id = zone.id
        self.zone_root = zone.root
        assert self.zone_id is not None
        assert self.zone_root is not None
        self.deleted = deleted
        self.dirty = dirty
        self.managed = managed

    def __repr__(self):
        return "<{} id={} {}:{} {}>".format(
            type(self).__name__, self.id, self.type, self.name, self.values)

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
    def is_hidden(self):
        return self.name.startswith(RECORD_PREFIX)

    def is_member_of(self, policy):
        return self.name.startswith('{}_{}'.format(RECORD_PREFIX, policy.name))

    def save(self):
        self.zone.process_records([self])

    def is_subset(self, other):
        return self.to_aws().items() <= other.to_aws().items()

    def validate_unique(self):
        """You're not allowed to have a CNAME clash with any other type of record"""
        if self.deleted:
            # allow deleting any conflicting record
            return
        if self.type == 'CNAME':
            clashing = tuple((self.name, r_type) for r_type in RECORD_TYPES)
        else:
            clashing = ((self.name, 'CNAME'), )
        for record in self.zone.db_zone.records:
            for other in clashing:
                if (record.name, record.type) == other and record.id != self.id:
                    raise ValidationError(
                        {'name': "A {} record of the same name already exists.".format(other[1])})

    def clean(self):
        pass

    def clean_fields(self):
        pass

    def full_clean(self):
        self.clean_fields()
        self.clean()
        self.validate_unique()


class Record(BaseRecord):
    def __init__(self, type=None, **kwa):
        super().__init__(**kwa)
        self.type = type


class PolicyRecord(BaseRecord):
    def __init__(self, zone, policy_record=None, policy=None, dirty=None,
                 deleted=None, created=None):
        if policy is None:
            policy = policy_record.policy
        if dirty is None:
            dirty = policy_record.dirty
        if deleted is None:
            deleted = policy_record.deleted

        self.db_policy_record = policy_record
        self._policy = None
        self.policy = policy
        self.zone = zone

        super().__init__(
            name=self.db_policy_record.name,
            zone=zone,
            alias_target={
                'HostedZoneId': zone.id,
                'DNSName': '{}_{}.{}'.format(RECORD_PREFIX, self.policy.name, zone.root),
                'EvaluateTargetHealth': False
            },
            deleted=deleted,
            dirty=dirty,
            created=created,
        )

    def save(self):
        if self.deleted:
            # The record will be deleted
            self.db_policy_record.deleted = True
            self.db_policy_record.dirty = True
        else:
            # Update policy for this record.
            self.db_policy_record.policy_id = self.policy.id
            self.db_policy_record.deleted = False  # clear deleted flag
            self.db_policy_record.dirty = True
        self.db_policy_record.full_clean()
        self.db_policy_record.save()

    def reconcile(self):
        # upsert or delete the top level alias
        if self.deleted:
            if self._top_level_record.id in self.zone.records():
                self.zone.process_records([self])
            self.db_policy_record.delete()
        else:
            existing_alias = self._existing_alias
            if (existing_alias is None or not self._top_level_record.is_subset(existing_alias)):
                self.zone.process_records([self])
            self.db_policy_record.dirty = False  # mark as clean
            self.db_policy_record.save()

    @memoized_property
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

    @memoized_property
    def _existing_alias(self):
        return self.zone.records().get(self.id)

    def to_aws(self):
        return self._top_level_record.to_aws()

    @property
    def id(self):
        return self._top_level_record.id

    @property
    def values(self):
        return [str(self.policy.id)]

    @values.setter
    def values(self, values):
        (pol_id, ) = values
        policy = route53.Policy(policy=models.Policy.objects.get(id=pol_id), zone=self.zone)
        self.policy = policy

    @property
    def type(self):
        return POLICY_ROUTED

    @property
    def policy(self):
        return self._policy

    @policy.setter
    def policy(self, value):
        if value is None:
            self.db_policy_record.policy = None
        else:
            self.db_policy_record.policy_id = value.id
        self._policy = value


def record_factory(zone, created=None, **validated_data):
    record_type = validated_data.pop('type')
    if record_type == POLICY_ROUTED:
        assert len(validated_data['values']) == 1
        policy_id = validated_data['values'][0]
        try:
            policy = models.Policy.objects.get(id=policy_id)
        except models.Policy.DoesNotExist:
            raise SuspiciousOperation("Policy {}  does not exists.".format(
                policy_id))
        record_model = models.PolicyRecord.new_or_deleted(name=validated_data['name'], zone=zone)
        obj = PolicyRecord(
            policy_record=record_model,
            zone=zone.r53_zone,
            policy=policy,
            dirty=True,
            created=created,
        )
    else:
        obj = Record(zone=zone.r53_zone, type=record_type, created=created, **validated_data)
    return obj
