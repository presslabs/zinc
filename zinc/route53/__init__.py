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
