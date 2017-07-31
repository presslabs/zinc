from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler

from zinc.route53.client import get_client


def custom_exception_handler(excp, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    if isinstance(excp, get_client().exceptions.ThrottlingException):
        excp = Throttled()
    return exception_handler(excp, context)
