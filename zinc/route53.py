import json
import uuid
import logging

import boto3
from boto3.session import Session
from botocore.exceptions import ClientError
from django.conf import settings

from django_project.vendors import hashids

AWS_KEY = getattr(settings, 'AWS_KEY', '')
AWS_SECRET = getattr(settings, 'AWS_SECRET', '')

# Pass '-' as if AWS_KEY from settings is empty
# because boto will look into '~/.aws/config' file if
# AWS_KEY or AWS_SECRET are not defined, which is the default
# and can mistaknely use production keys

client = boto3.client(
    service_name='route53',
    aws_access_key_id=AWS_KEY or '-',
    aws_secret_access_key=AWS_SECRET or '-'
)

logger = logging.getLogger('zinc.route53')


def _get_aws_regions():
    """Retrieve a list of region tuples available in AWS EC2."""
    return Session().get_available_regions('ec2')


def get_local_aws_regions():
    """Use `_get_aws_regions` and update this list."""
    return ['us-east-1', 'us-west-1', 'us-west-2', 'ap-northeast-1',
            'ap-northeast-2', 'ap-south-1', 'ap-southeast-1',
            'ap-southeast-2', 'sa-east-1', 'eu-west-1', 'eu-central-1']


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
            record.setdefault('id', hashids.encode_record(record, self.zone_record.route53_zone.id))
            self.add_record_changes(record, key=record['id'])

    def add_record_changes(self, record, key=None):
        rrs = RecordHandler.encode(record, self.root)
        if not key or key not in self.records():
            action = 'CREATE'
        else:
            action = 'DELETE' if record.get('delete', False) else 'UPSERT'

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

    def records(self, rfilter=None):
        self._cache_aws_records()
        entries = {}

        for aws_record in self._aws_records:
            record = RecordHandler.decode(aws_record, self.root, self.id)

            if record:
                if rfilter and not rfilter(record):
                    continue
                else:
                    entries[record['id']] = record

        return entries

    @property
    def exists(self):
        self._cache_aws_records()
        return self._exists

    @property
    def ns(self):
        return self.records(lambda record: (record['type'] == 'NS' and record['name'] == '@'))

    def _cache_aws_records(self):
        if self._aws_records is not None:
            return
        if not self.id:
            return
        try:
            response = client.list_resource_record_sets(HostedZoneId=self.id)
        except ClientError as excp:
            if excp.response['Error']['Code'] == 'NoSuchHostedZone':
                self._aws_records = []
                self._exists = False
        else:
            self._aws_records = response['ResourceRecordSets']
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


class RecordHandler:
    @classmethod
    def _add_root(cls, name, root):
        return root if name == '@' else '{}.{}'.format(name, root)

    @classmethod
    def _strip_root(cls, name, root):
        return '@' if name == root else name.replace('.' + root, '')

    @classmethod
    def encode(cls, record, root):
        encoded_record = {
            'Name': cls._add_root(record['name'], root),
            'Type': record['type'],
        }
        if 'values' in record:
            if record['type'] == 'TXT':
                # Encode json escape.
                encoded_record['ResourceRecords'] = [{'Value': json.dumps(value)}
                                                     for value in record['values']]
            else:
                encoded_record['ResourceRecords'] = [{'Value': value} for value in record['values']]

        if 'ttl' in record:
            encoded_record['TTL'] = record['ttl']

        if 'AliasTarget' in record:
            encoded_record['AliasTarget'] = {
                'DNSName': cls._add_root(record['AliasTarget']['DNSName'], root),
                'EvaluateTargetHealth': record['AliasTarget']['EvaluateTargetHealth'],
                'HostedZoneId': record['AliasTarget']['HostedZoneId'],
            }

        for extra in ['Weight', 'Region', 'SetIdentifier',
                      'HealthCheckId', 'TrafficPolicyInstanceId']:
            if extra in record:
                encoded_record[extra] = record[extra]

        return encoded_record

    @classmethod
    def decode(cls, record, root, route53_id):
        # Determine if a R53 DNS record is of type ALIAS
        def alias_record(record):
            return 'AliasTarget' in record.keys()

        # Determine if a record is the NS or SOA record of the root domain
        def root_ns_soa(record, root):
            return record['Name'] == root and record['Type'] in ['NS', 'SOA']

        decoded_record = {
            'name': cls._strip_root(record['Name'], root),
            'type': record['Type'],
            'managed': (
                (record.get('SetIdentifier', False) and True) or
                root_ns_soa(record, root) or (alias_record(record))
            ),
        }

        if 'TTL' in record:
            decoded_record['ttl'] = record['TTL']

        if alias_record(record):
            decoded_record['AliasTarget'] = {
                'DNSName': cls._strip_root(record['AliasTarget']['DNSName'], root),
                'EvaluateTargetHealth': record['AliasTarget']['EvaluateTargetHealth'],
                'HostedZoneId': record['AliasTarget']['HostedZoneId']
            }
        elif record['Type'] == 'TXT':
            # Decode json escaped strings
            decoded_record['values'] = [json.loads('[%s]' % value['Value'])[0]
                                        for value in record.get('ResourceRecords', [])]
        else:
            decoded_record['values'] = [value['Value'] for value in
                                        record.get('ResourceRecords', [])]

        for extra in ['Weight', 'Region', 'SetIdentifier',
                      'HealthCheckId', 'TrafficPolicyInstanceId']:
            if extra in record:
                decoded_record[extra] = record[extra]

        set_id = hashids.encode_record(decoded_record, route53_id)
        decoded_record['id'] = set_id

        return decoded_record


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
