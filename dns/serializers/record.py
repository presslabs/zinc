from collections import OrderedDict
from django.conf import settings
from rest_framework.fields import (CharField, ChoiceField,
                                   IntegerField, ListField, SerializerMethodField)
from rest_framework.serializers import Serializer
from rest_framework.exceptions import ValidationError

from dns.exceptions import UnprocessableEntity
from dns.models import RECORD_PREFIX

HASHIDS_MIN_LENGTH = getattr(settings, 'HASHIDS_MIN_LENGTH', 7)


class RecordSerializer(Serializer):
    RECORD_TYPES = [
        'A', 'AAAA', 'CNAME', 'MX', 'TXT',
        'SPF', 'SRV', 'NS', 'SOA', 'POLICY_ROUTED'
    ]

    name = CharField(max_length=255)
    type = ChoiceField(choices=[(type, type) for type in RECORD_TYPES])
    ttl = IntegerField(allow_null=True, min_value=300, required=False)
    values = ListField(child=CharField(), required=True)
    dirty = SerializerMethodField()

    def get_dirty(self, obj):
        return obj.get('dirty', False)

    def create(self, validated_data):
        raise NotImplementedError('Records can`t be created individually')

    def update(self, **validated_data):
        raise NotImplementedError('Records can`t be saved individually')

    def validate_name(self, value):
        if value.startswith(RECORD_PREFIX):
            raise ValidationError(
                ('Record {} can\'t start with {}. '
                 'It\'s a reserved prefix.').format(value, RECORD_PREFIX)
            )
        return value

    def to_internal_value(self, data):
        if data.get('delete', False):
            data = OrderedDict(data)
        else:
            data = super(RecordSerializer, self).to_internal_value(data)

        return data

    def validate(self, data):
        if data['type'] != 'POLICY_ROUTED':
            if not data.get('ttl', False):
                raise ValidationError('Field \'ttl\' is required. '
                                      'If record type is not POLICY_REOCRD.')

        else:
            if not len(data['values']) == 1:
                raise ValidationError('For POLICY_ROUTED record values list '
                                      'should contain just one element.')
        return data
