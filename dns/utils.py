from boto3.session import Session


def get_regions():
    '''Retrieve a list of region tuples available in AWS EC2'''
    return [(region, region) for region in Session().get_available_regions('ec2')]
