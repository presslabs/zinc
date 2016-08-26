from django.core.exceptions import ValidationError
from django.db import models

from dns.validators import validate_domain
from dns.utils import route53


class Zone(models.Model):
    root = models.CharField(
        max_length=255,
        validators=[validate_domain]
    )
    route53_id = models.CharField(max_length=32, unique=True, editable=False)
    caller_reference = models.UUIDField(editable=False, unique=True)

    def clean(self):
        if self.route53_id:
            return

        try:
            zone = route53.Zone.create(self.root)
        except route53.ClientError as e:
            raise ValidationError(str(e), 400)

        self.route53_id = zone.id
        self.caller_reference = zone.caller_reference

    def __str__(self):
        return '{} {}'.format(self.pk, self.root)

    def __unicode__(self):
        return self.__str__()
