import random

import boto3
import botocore.retryhandler
from django.conf import settings


def delay_exponential(base, *a, **kwa):
    """
    Override botocore's delay_exponential retry strategy, to ensure min delay is non-zero.
    We want to use a random base between 0.2 and 0.8. Final progressions are:
    min: [0.2, 0.4, 0.8, 1.6,  3.2] - 6.2 s
    max: [0.8, 1.6, 3.2, 6.4, 12.8] - 24.8 s
    """
    if base == 'rand':
        # 1 / 1.(6) == 0.6
        base = 0.2 + random.random() / 1.666666666666666666
    return botocore.retryhandler._orig_delay_exponential(base, *a, **kwa)


# we monkeypatch the retry handler because the original logic in botocore is to optimistic
# in the case of a random backoff (they pick a base in the 0-1.0 second interval)
botocore.retryhandler._orig_delay_exponential = botocore.retryhandler.delay_exponential
botocore.retryhandler.delay_exponential = delay_exponential

AWS_KEY = getattr(settings, 'AWS_KEY', '')
AWS_SECRET = getattr(settings, 'AWS_SECRET', '')

# Pass '-' as if AWS_KEY from settings is empty
# because boto will look into '~/.aws/config' file if
# AWS_KEY or AWS_SECRET are not defined, which is the default
# and can mistaknely use production keys

_client = boto3.client(
    service_name='route53',
    aws_access_key_id=AWS_KEY or '-',
    aws_secret_access_key=AWS_SECRET or '-',
)


def get_client():
    return _client
