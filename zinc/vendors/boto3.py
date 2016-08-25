from django.conf import settings

import boto3
from boto3.session import Session


AWS_KEY = getattr(settings, 'AWS_KEY', '')
AWS_SECRET = getattr(settings, 'AWS_SECRET', '')

client = boto3.client(
    service_name='route53',
    aws_access_key_id=AWS_KEY,
    aws_secret_access_key=AWS_SECRET
)


def get_regions():
    """Retrieve a list of region tuples available in AWS EC2"""
    return Session().get_available_regions('ec2')
