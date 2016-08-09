from boto.ec2 import get_regions
from django.core.validators import RegexValidator


validate_hostname = RegexValidator(
    regex=r'^(?=[a-z0-9\-\.]{1,253}$)([a-z0-9](([a-z0-9\-]){,61}[a-z0-9])?\.)*([a-z0-9](([a-z0-9\-]){,61}[a-z0-9])?)$',
    message=u'Invalid hostname',
    code='invalid_hostname'
)


def get_ip_regions():
    '''Retrieve a list of region tuples available in AWS EC2'''
    return [(r.name, r.name) for r in get_regions(service_name='ec2')]
