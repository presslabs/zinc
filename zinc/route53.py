import json
import uuid
import logging
import random

import boto3
from boto3.session import Session
import botocore.retryhandler
from botocore.exceptions import ClientError
from django.conf import settings


def delay_exponential(base, *a, **kwa):
    """
    Override botocore's delay_exponential retry strategy, to ensure min delay is non-zero.
    We want to use a random base between 0.2 and 0.8. Final progressions are:
    min: [0.2, 0.4, 0.8, 1.6,  3.2] - 6.2 s
    max: [0.8, 1.6, 3.2, 6.4, 12.8] - 24.8 s
    """
    if base == 'rand':
        # 1 / 1.(6) == 0.6
        base = 0.2 + random.random() / 1.666666666666666666
    return botocore.retryhandler._orig_delay_exponential(base, *a, **kwa)


# we monkeypatch the retry handler because the original logic in botocore is to optimistic
# in the case of a random backoff (they pick a base in the 0-1.0 second interval)
botocore.retryhandler._orig_delay_exponential = botocore.retryhandler.delay_exponential
botocore.retryhandler.delay_exponential = delay_exponential

AWS_KEY = getattr(settings, 'AWS_KEY', '')
AWS_SECRET = getattr(settings, 'AWS_SECRET', '')

# Pass '-' as if AWS_KEY from settings is empty
# because boto will look into '~/.aws/config' file if
# AWS_KEY or AWS_SECRET are not defined, which is the default
# and can mistaknely use production keys

client = boto3.client(
    service_name='route53',
    aws_access_key_id=AWS_KEY or '-',
    aws_secret_access_key=AWS_SECRET or '-',
)

logger = logging.getLogger('zinc.route53')


def _get_aws_regions():
    """Retrieve a list of region tuples available in AWS EC2."""
    return Session().get_available_regions('ec2')


def get_local_aws_region_choices():
    return (
        ('us-east-1', 'US East (N. Virginia)'),
        ('us-east-2', 'US East (Ohio)'),
        ('us-west-1', 'US West (N. California)'),
        ('us-west-2', 'US West (Oregon)'),
        ('ap-south-1', 'Asia Pacific (Mumbai)'),
        ('ap-northeast-2', 'Asia Pacific (Seoul)'),
        ('ap-southeast-1', 'Asia Pacific (Singapore)'),
        ('ap-southeast-2', 'Asia Pacific (Sydney)'),
        ('ap-northeast-1', 'Asia Pacific (Tokyo)'),
        ('ca-central-1', 'Canada (Central)'),
        ('cn-north-1', 'China (Beijing)'),
        ('eu-central-1', 'EU (Frankfurt)'),
        ('eu-west-1', 'EU (Ireland)'),
        ('eu-west-2', 'EU (London)'),
        ('sa-east-1', 'South America (São Paulo)'),
    )


def get_local_aws_regions():
    return [region[0] for region in get_local_aws_region_choices()]


def generate_caller_ref():
    return 'zinc {}'.format(uuid.uuid4())


class Zone(object):

    def __init__(self, zone_record):
        self.zone_record = zone_record
        self._aws_records = None
        self._exists = None
        self._change_batch = []

    @property
    def id(self):
        return self.zone_record.route53_id

    @property
    def root(self):
        return self.zone_record.root

    def add_records(self, records):
        for record in records:
            self.add_record_changes(record, key=record.id)

    def add_record_changes(self, record, key=None):
        rrs = record.encode()
        if not key or key not in self.records():
            action = 'CREATE'
        else:
            action = 'DELETE' if record.deleted else 'UPSERT'

        self._change_batch.append({
            'Action': action,
            'ResourceRecordSet': rrs
        })

    def _reset_change_batch(self):
        self._change_batch = []

    def commit(self):
        if not self._change_batch:
            return

        client.change_resource_record_sets(
            HostedZoneId=self.id,
            ChangeBatch={'Changes': self._change_batch}
        )
        # clear cache
        self._reset_change_batch()
        self._clear_cache()

    def records(self):
        self._cache_aws_records()
        entries = {}
        for aws_record in self._aws_records or []:
            record = Record.from_aws_record(aws_record, root=self.root, route53_id=self.id)
            if record:
                entries[record.record_hash] = record
        return entries

    @property
    def exists(self):
        self._cache_aws_records()
        return self._exists

    @property
    def ns(self):
        if not self.exists:
            return None
        ns = [record for record in self.records().values()
              if record.type == 'NS' and record.name == '@']
        assert len(ns) == 1
        return ns[0]

    def _cache_aws_records(self):
        if self._aws_records is not None:
            return
        if not self.id:
            return
        paginator = client.get_paginator('list_resource_record_sets')
        records = []
        try:
            for page in paginator.paginate(HostedZoneId=self.id):
                records.extend(page['ResourceRecordSets'])
        except ClientError as excp:
            if excp.response['Error']['Code'] != 'NoSuchHostedZone':
                raise
            self._aws_records = []
            self._exists = False
        else:
            self._aws_records = records
            self._exists = True

    def _clear_cache(self):
        self._aws_records = None
        self._exists = None

    def delete(self):
        if self.exists:
            self._delete_records()
            client.delete_hosted_zone(Id=self.id)
        self.zone_record.delete()

    def _delete_records(self):
        self._cache_aws_records()
        zone_root = self.root

        to_delete = []
        for record in self._aws_records:
            if record['Type'] in ['NS', 'SOA'] and record['Name'] == zone_root:
                continue

            to_delete.append({
                'Action': 'DELETE',
                'ResourceRecordSet': record
            })

        if to_delete:
            client.change_resource_record_sets(
                HostedZoneId=self.id,
                ChangeBatch={
                    'Changes': to_delete
                })

    def create(self):
        if self.zone_record.caller_reference is None:
            self.zone_record.caller_reference = uuid.uuid4()
            self.zone_record.save()
        zone = client.create_hosted_zone(
            Name=self.root,
            CallerReference=str(self.zone_record.caller_reference),
            HostedZoneConfig={
                'Comment': 'zinc'
            }
        )
        self.zone_record.route53_id = zone['HostedZone']['Id']
        self.zone_record.save()

    def reconcile(self):
        if self.zone_record.deleted:
            self.delete()
        elif self.zone_record.route53_id is None:
            self.create()
        elif not self.exists:
            try:
                self.create()
            except ClientError as excp:
                if excp.response['Error']['Code'] != 'HostedZoneAlreadyExists':
                    raise
                # This can happen if a zone was manually deleted from AWS.
                # Create will fail because we re-use the caller_reference
                self.zone_record.caller_reference = None
                self.zone_record.save()
                self.create()

    @classmethod
    def reconcile_multiple(cls, zones):
        for zone_record in zones:
            zone = cls(zone_record)
            try:
                zone.reconcile()
            except ClientError:
                logger.exception("Error while handling %s", zone_record.name)


class Record:
    _attr_mapping = dict([
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
    _r53_to_obj = {v: k for k, v in _attr_mapping.items()}

    def __init__(self, name=None, type=None, alias_target=None, deleted=False, dirty=False,
                 health_check_id=None, managed=False, region=None, set_identifier=None,
                 traffic_policy_instance_id=None, ttl=None, values=None, weight=None,
                 zone=None, zone_id=None, zone_root=None):
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
        if zone is None:
            self.zone_id = zone_id
            self.zone_root = zone_root
        else:
            self.zone_id = zone.route53_id
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
    def from_aws_record(cls, record, root, route53_id):
        # Determine if a R53 DNS record is of type ALIAS
        def alias_record(record):
            return 'AliasTarget' in record.keys()

        # Determine if a record is the NS or SOA record of the root domain
        def root_ns_soa(record, root):
            return record['Name'] == root and record['Type'] in ['NS', 'SOA']

        kwargs = {}
        for attr_name in ['weight', 'region', 'set_identifier', 'health_check_id',
                          'traffic_policy_instance_id']:
            kwargs[attr_name] = record.get(cls._attr_mapping[attr_name], None)

        new = cls(zone_id=route53_id, zone_root=root, **kwargs)
        new.name = cls._strip_root(record['Name'], root)
        new.type = record['Type']
        new.managed = ((record.get('SetIdentifier', False)) or
                       root_ns_soa(record, root) or (alias_record(record)))

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
    def record_hash(self):
        from django_project.vendors.hashids import _encode
        from django_project import get_record_type
        zone_hash = _encode(self.zone_id)
        record_hash = _encode(self.name, self.type, self.set_identifier)
        return 'Z{zone}Z{type}Z{id}'.format(
            zone=zone_hash, type=get_record_type(self.type), id=record_hash)

    @property
    def id(self):
        return self.record_hash

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


class HealthCheck:
    def __init__(self, ip):
        self.ip = ip
        self._aws_data = None

    @property
    def exists(self):
        self._load()
        return self._aws_data is not None

    @property
    def id(self):
        self._load()
        return self._aws_data.get('Id')

    def _load(self):
        if self._aws_data is not None:
            return
        if self.ip.healthcheck_id is not None:
            try:
                health_check = client.get_health_check(HealthCheckId=self.ip.healthcheck_id)
                self._aws_data = health_check.get('HealthCheck')
            except ClientError as exception:
                if exception.response['Error']['Code'] != 'NoSuchHealthCheck':
                    raise  # re-raise any error, we only handle non-existant health checks

    @property
    def desired_config(self):
        config = {
            'IPAddress': self.ip.ip,
        }
        config.update(settings.HEALTH_CHECK_CONFIG)
        return config

    @property
    def config(self):
        self._load()
        return self._aws_data.get('HealthCheckConfig')

    def create(self):
        if self.ip.healthcheck_caller_reference is None:
            self.ip.healthcheck_caller_reference = uuid.uuid4()
            logger.info("%-15s new caller_reference %s",
                        self.ip.ip, self.ip.healthcheck_caller_reference)
            self.ip.save()
        resp = client.create_health_check(
            CallerReference=str(self.ip.healthcheck_caller_reference),
            HealthCheckConfig=self.desired_config
        )
        self.ip.healthcheck_id = resp['HealthCheck']['Id']
        logger.info("%-15s created hc: %s", self.ip.ip, self.ip.healthcheck_id)
        self.ip.save()

    def delete(self):
        if self.exists:
            logger.info("%-15s delete hc: %s", self.ip.ip, self.ip.healthcheck_id)
            client.delete_health_check(HealthCheckId=self.id)
            self.ip.healthcheck_caller_reference = None
            self.ip.save(update_fields=['healthcheck_caller_reference'])

    def reconcile(self):
        if self.ip.deleted:
            self.delete()
            self.ip.delete()
        elif self.exists:
            # if the desired config is not a subset of the current config
            if not self.desired_config.items() <= self.config.items():
                self.delete()
                self.create()
            else:
                logger.info("%-15s nothing to do", self.ip.ip)
        else:
            try:
                self.create()
            except ClientError as excp:
                if excp.response['Error']['Code'] != 'HealthCheckAlreadyExists':
                    raise
                self.ip.healthcheck_caller_reference = None
                self.ip.save()
                self.create()

    @classmethod
    def reconcile_for_ips(cls, ips):
        checks = [cls(ip) for ip in ips]
        for check in checks:
            try:
                check.reconcile()
            except ClientError:
                logger.exception("Error while handling %s", check.ip.friendly_name)
