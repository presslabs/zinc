from boto.ec2 import get_regions


def get_ip_regions():
    '''Retrieve a list of region tuples available in AWS EC2'''
    return [(r.name, r.name) for r in get_regions(service_name='ec2')]
