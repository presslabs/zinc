import uuid
import boto3
import datetime

from botocore.exceptions import ClientError
from boto3.session import Session
from django.conf import settings

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
        self.id = id
        self.root = root
        self.caller_reference = caller_reference
        self._aws_records = []

    @property
    def ns(self):
        root = self._aws_root()
        return self._records(
            lambda record: True if (record['Type'] == 'NS' and
                                    record['Name'] == root) else False)[0]

    @property
    def records(self):
        root = self._aws_root()
        return self._records(
            lambda record: True if not (record['Type'] == 'NS' and
                                        record['Name'] == root) else False)

    def _records(self, chooser=None):
        self._cache_aws_records()
        root = self._aws_root()

        entries = []
        for record in self._aws_records:
            if chooser and not chooser(record):
                continue
            else:
                entries.append(
                    Record(
                        name='@' if record['Name'] == root else record['Name'].replace(root, ''),
                        record_type=record['Type'],
                        values=[r['Value'] for r in record['ResourceRecords']],
                        ttl=record['TTL'],
                        managed=True if record['Type'] in ['NS', 'POLICY_ROUTED'] else False
                    )
                )

        return entries

    def _cache_aws_records(self):
        if self._aws_records:
            return

        try:
            response = client.list_resource_record_sets(HostedZoneId=self.id)
            self._aws_records = response['ResourceRecordSets']
        except Exception:
            self._aws_records = []

    def _aws_root(self):
        return '{}.'.format(self.root)

    def delete(self):
        self._delete_records()
        client.delete_hosted_zone(Id=self.id)

    def _delete_records(self):
        self._cache_aws_records()
        zone_root = self._aws_root()

        to_delete = []
        for record in self._aws_records:
            if record['Type'] in ['NS', 'SOA'] and \
                            record['Name'] == zone_root:
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

    @staticmethod
    def create(root):
        ref = uuid.uuid4()
        zone = client.create_hosted_zone(
            Name=root,
            CallerReference='zinc {} {}'.format(ref, datetime.datetime.now()),
            HostedZoneConfig={
                'Comment': 'zinc'
            }
        )

        id = zone['HostedZone']['Id'].split('/')[2]

        return Zone(id, root, ref)


class Record(object):
    def __init__(self, name, record_type, values, ttl, managed, dirty=False):
        self.name = name
        self.record_type = record_type
        self.values = values
        self.ttl = ttl
        self.managed = managed
        self.dirty = dirty
