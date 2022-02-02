from boto3.session import Session

from .record import Record, PolicyRecord, record_factory  # noqa: F401
from .policy import Policy  # noqa: F401
from .zone import Zone  # noqa: F401
from .health_check import HealthCheck  # noqa: F401


def _get_aws_regions():
    """Retrieve a list of region tuples available in AWS EC2."""
    return Session().get_available_regions('ec2')


def get_local_aws_region_choices():
    return (
        ('af-south-1', 'Africa (Cape Town)'),
        ('ap-east-1', 'Asia Pacific (Hong Kong)'),
        ('ap-northeast-1', 'Asia Pacific (Tokyo)'),
        ('ap-northeast-2', 'Asia Pacific (Seoul)'),
        ('ap-northeast-3', 'Asia Pacific (Osaka-Local)'),
        ('ap-south-1', 'Asia Pacific (Mumbai)'),
        ('ap-southeast-1', 'Asia Pacific (Singapore)'),
        ('ap-southeast-2', 'Asia Pacific (Sydney)'),
        ('ap-southeast-3', 'Asia Pacific (Jakarta)'),
        ('ca-central-1', 'Canada (Central)'),
        ('cn-north-1', 'China (Beijing)'),
        ('cn-northwest-1', 'China (Ningxia)'),
        ('eu-central-1', 'Europe (Frankfurt)'),
        ('eu-north-1', 'Europe (Stockholm)'),
        ('eu-south-1', 'Europe (Milan)'),
        ('eu-west-1', 'Europe (Ireland)'),
        ('eu-west-2', 'Europe (London)'),
        ('eu-west-3', 'Europe (Paris)'),
        ('me-south-1', 'Middle East (Bahrain)'),
        ('sa-east-1', 'South America (São Paulo)'),
        ('us-east-1', 'US East (N. Virginia)'),
        ('us-east-2', 'US East (Ohio)'),
        ('us-west-1', 'US West (N. California)'),
        ('us-west-2', 'US West (Oregon)'),
    )


def get_local_aws_regions():
    return [region[0] for region in get_local_aws_region_choices()]
