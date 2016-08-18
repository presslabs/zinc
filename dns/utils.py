from boto3.session import Session


def get_regions():
    """Retrieve a list of region tuples available in AWS EC2"""
    return [(region, region) for region in Session().get_available_regions('ec2')]


def list_overlap(lst_1, lst_2):
    for member in lst_1:
        if member in lst_2:
            return True
    return False
