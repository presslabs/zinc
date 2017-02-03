import uuid
import boto3
import datetime
from abc import ABCMeta

from botocore.exceptions import ClientError
from boto3.session import Session
from django.conf import settings

from django.apps import apps
from zinc.vendors import hashids

AWS_KEY = getattr(settings, 'AWS_KEY', '')
AWS_SECRET = getattr(settings, 'AWS_SECRET', '')

client = boto3.client(
    service_name='route53',
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET
)


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
    def __init__(self, id=None, root='', caller_reference=None):
        if id.startswith('/hostedzone/'):
            id = id[len('/hostedzone/'):]
        self.id = id
        self.root = (root)
        self.caller_reference = caller_reference
        self._aws_records = []
        self._change_batch = []

    def add_records(self, records):
        for record_hash, record in records.items():
            self.add_record_changes(record, key=record_hash)

    def add_record_changes(self, record, key=None):
        if not key or key not in self.records():
            action = 'CREATE'
        else:
            action = 'DELETE' if record.get('delete', False) else 'UPSERT'

        self._change_batch.append({
            'Action': action,
            'ResourceRecordSet': RecordHandler.encode(record, self.root)
        })

    def _reset_change_batch(self):
        self._change_batch = []

    def commit(self):
        if not self._change_batch:
            return

        try:
            client.change_resource_record_sets(
                HostedZoneId=self.id,
                ChangeBatch={'Changes': self._change_batch}
            )
            # clear cache
            self._reset_change_batch()
            self._aws_records = []
        except ClientError as error:
            print('Error on commit({}): {}, changes: {}'.format(
                self.root, error, self._change_batch))
            raise

    def records(self, rfilter=None):
        return self._records(rfilter)

    def _records(self, rfilter):
        self._cache_aws_records()
        entries = {}

        for aws_record in self._aws_records:
            record = RecordHandler.decode(aws_record, self.root, self.id)

            if record:
                if rfilter and not rfilter(record):
                    continue
                else:
                    entries[record['set_id']] = record

        return entries

    @property
    def ns(self):
        return self._records(lambda record: (record['type'] == 'NS' and record['name'] == '@'))

    def _cache_aws_records(self):
        if self._aws_records:
            return

        response = client.list_resource_record_sets(HostedZoneId=self.id)
        self._aws_records = response['ResourceRecordSets']

    def delete(self):
        self._delete_records()
        client.delete_hosted_zone(Id=self.id)

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

    @classmethod
    def create(cls, root):
        ref = uuid.uuid4()
        zone = client.create_hosted_zone(
            Name=root,
            CallerReference='zinc {} {}'.format(ref, datetime.datetime.now()),
            HostedZoneConfig={
                'Comment': 'zinc'
            }
        )

        id = zone['HostedZone']['Id']

        return cls(id, root, ref)


class RecordHandler(ABCMeta):
    @classmethod
    def _add_root(cls, name, root):
        return root if name == '@' else '{}.{}'.format(name, root)

    @classmethod
    def _strip_root(cls, name, root):
        return '@' if name == root else name.replace('.' + root, '')

    @classmethod
    def encode(cls, record, root):
        delete = record.get('delete', False)
        if delete:
            del record['delete']

        encoded_record = {
            'Name': cls._add_root(record['name'], root),
            'Type': record['type'],
        }
        if 'values' in record:
            encoded_record['ResourceRecords'] = [{'Value': v} for v in record['values']]

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
        """
        Hide all '_policy' records
        """
        if record['Name'].startswith('_policy'):
            return None

        """
        Determine if a R53 DNS record is of type ALIAS
        """
        def alias_record(record):
            return 'AliasTarget' in record.keys()

        """
        Determine if a R53 DNS record is actually a policy record
        """
        def policy_record(record, route53_id):
            PolicyRecord = apps.get_model(app_label='dns', model_name='PolicyRecord')
            return PolicyRecord.objects.filter(
                                            name=cls._strip_root(record['Name'], root),
                                            zone__route53_id=route53_id
                                        ).exists()

        """
        Determine if a record is the NS or SOA record of the root domain
        """
        def root_ns_soa(record, root):
            return record['Name'] == root and record['Type'] in ['NS', 'SOA']

        set_id = record.get('SetIdentifier', None)
        set_id = set_id or hashids.encode(record['Name'], record['Type'], set_id)

        decoded_record = {
            'name': cls._strip_root(record['Name'], root),
            'type': 'POLICY_ROUTED' if policy_record(record, route53_id) else record['Type'],
            'managed': (
                (record.get('SetIdentifier', False) and True) or
                root_ns_soa(record, root) or
                (alias_record(record) and not policy_record(record, route53_id))
            ),
            'set_id': set_id
        }

        if decoded_record['type'] != 'POLICY_ROUTED':
            if alias_record(record):
                decoded_record['values'] = ['ALIAS {}'.format(record['AliasTarget']['DNSName'])]
            else:
                decoded_record['values'] = [r['Value'] for r in record.get('ResourceRecords', [])]
                if 'TTL' in record:
                    decoded_record['ttl'] = record['TTL']

        return decoded_record
