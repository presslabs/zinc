import string
import random

import time

from botocore.exceptions import ClientError
from django.core.exceptions import ValidationError
from django.db import models

from dns.validators import validate_domain
from zinc.vendors.boto3 import client


class Zone(models.Model):
    root = models.CharField(
        max_length=255,
        validators=[validate_domain]
    )
    route53_id = models.CharField(max_length=32, unique=True, editable=False)

    def full_clean(self, exclude=None, validate_unique=True):
        try:
            super(Zone, self).full_clean(exclude=exclude, validate_unique=validate_unique)
            self.clean_route53_id()
        except ValidationError as e:
            raise e
        except ClientError as e:
            raise ValidationError(str(e), 400)

    def clean_route53_id(self):
        if self.route53_id:
            return

        ref = 'zinc{}{}{}{}'.format(
            time.time(),
            random.choice(string.ascii_letters),
            random.choice(string.ascii_letters),
            random.choice(string.ascii_letters),
        )

        # May through exceptions, caller has to safeguard agains
        response = client.create_hosted_zone(
            Name=self.root,
            CallerReference=ref
        )

        self.route53_id = response['HostedZone']['Id'].split('/')[2]

    def __str__(self):
        return '{} {}'.format(self.pk, self.root)

    def __unicode__(self):
        return self.__str__()
