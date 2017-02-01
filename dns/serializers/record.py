from collections import OrderedDict
from django.conf import settings
from rest_framework.exceptions import ValidationError
from rest_framework.fields import (BooleanField, CharField, ChoiceField,
                                   DictField, IntegerField, ListField)
from rest_framework.serializers import Serializer

from dns.exceptions import UnprocessableEntity
from dns.models import Policy, PolicyRecord
from dns.utils import route53

HASHIDS_MIN_LENGTH = getattr(settings, 'HASHIDS_MIN_LENGTH', 7)


class RecordSerializer(Serializer):
    RECORD_TYPES = [
        'A', 'AAAA', 'CNAME', 'MX', 'TXT',
        'SPF', 'SRV', 'NS', 'SOA', 'POLICY_ROUTED'
    ]

    name = CharField(max_length=255)
    type = ChoiceField(choices=[(type, type) for type in RECORD_TYPES])
    ttl = IntegerField(allow_null=True, min_value=300, required=True)
    values = ListField(child=CharField(), required=True)
    set_id = CharField(min_length=HASHIDS_MIN_LENGTH, required=False)
    managed = BooleanField(default=False, read_only=True)
    dirty = BooleanField(default=False, read_only=True)
    delete = BooleanField(default=False, read_only=True, required=False)

    def __init__(self, *args, **kwargs):
        self.visible_fields = ['name', 'type', 'values', 'ttl']
        super(RecordSerializer, self).__init__(*args, **kwargs)

    def create(self, validated_data):
        raise NotImplementedError('Records can`t be created individually')

    def update(self, **validated_data):
        raise NotImplementedError('Records can`t be saved individually')

    def run_validation(self, data):
        if data.get('managed', False):
            raise UnprocessableEntity('Record {key} is managed.'.format(key=data['set_id']))
        return super(RecordSerializer, self).run_validation(data)

    def to_internal_value(self, data):
        if data.get('delete', False):
            data = OrderedDict({
                'delete': data['delete'],
                'name': data['name'],
                'set_id': data['set_id'],
                'type': data['type'],
                'values': data['values'],
                'ttl': data['ttl']
            })
        else:
            data = super(RecordSerializer, self).to_internal_value(data)

        return data

    def to_representation(self, value):
        return {
            key: val for key, val in value.items()
            if key in self.visible_fields
        }


class RecordSetSerializer(DictField):
    child = RecordSerializer(partial=False)
