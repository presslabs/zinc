from rest_framework.exceptions import Throttled

from zinc.route53.client import get_client


def boto_exception_middleware(get_response):
    def middleware(request):
        client = get_client()
        try:
            return get_response(request)
        except client.exceptions.ThrottlingException as excp:
            raise Throttled(detail=excp['Error']['Message']) from excp
    return middleware
