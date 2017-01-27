from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from hashid_field import HashidField

from dns.validators import validate_domain
from dns.utils import route53


class Zone(models.Model):
    root = models.CharField(max_length=255, validators=[validate_domain])
    route53_id = models.CharField(max_length=32, unique=True, editable=False)
    caller_reference = models.CharField(max_length=32, editable=False,
                                        unique=True)

    def __init__(self, *args, **kwargs):
        self._route53_instance = None
        super(Zone, self).__init__(*args, **kwargs)

    def clean(self):
        # TODO: this probably should be in save
        if self.route53_id is not None:
            return
        try:
            zone = route53.Zone.create(self.root)
        except route53.ClientError as e:
            raise ValidationError(str(e), 400)

        self.route53_id = zone.id
        self.caller_reference = zone.caller_reference

    @property
    def route53_zone(self):
        if not self._route53_instance:
            self._route53_instance = route53.Zone(id=self.route53_id, root=self.root)

        return self._route53_instance

    @property
    def records(self):
        return self.route53_zone.records()

    @records.setter
    def records(self, records):
        for _, record in records.items():
            self.route53_zone.add_record_changes(record)
        self.route53_zone.commit()

    def __str__(self):
        return '{} {}'.format(self.pk, self.root)

    def __unicode__(self):
        return self.__str__()
