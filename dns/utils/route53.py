import uuid
import boto3
import datetime

from botocore.exceptions import ClientError  # noqa
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
    def __init__(self, id=None, root=None, caller_reference=None):
        self.id = id
        self.root = root
        self.caller_reference = caller_reference

    def delete(self):
        self._delete_records()
        client.delete_hosted_zone(Id=self.id)

    def _delete_records(self):
        # TODO check NS SOA for default values and don't delete them! Not that you can..
        while True:
            response = client.list_resource_record_sets(HostedZoneId=self.id)

            to_delete = []
            for record in response['ResourceRecordSets']:
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

            if not response['IsTruncated']:
                break

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
