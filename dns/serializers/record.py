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
    ttl = IntegerField(default=None, allow_null=True, min_value=300, required=False)
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

    def update(self, zone, **validated_data):
        # TODO: remove this
        _zone = route53.Zone(id=zone.route53_id, root=zone.root)

        for key, record in validated_data.items():
            if key == 'new' and record['type'] == 'POLICY_ROUTED':
                try:
                    policy_pk = Policy.objects.values_list('pk', flat=True).get(name=record['name'])
                    precord_data = {
                        'name': record['name'],
                        'policy': policy_pk,
                        'zone': zone.pk
                    }

                    _, created = PolicyRecord.objects.get_or_create(**precord_data)
                    if not created:
                        raise ValidationError(
                            "Record '{name}' already exists.".format(name=record['name']))

                    # TODO Build the record tree
                except Policy.DoesNotExist:
                    msg = ("Can`t associate policy record '{name}'! The policy "
                           "named '{name}' does not exist.".format(name=record['name']))
                    raise ValidationError(msg)
                continue

            _zone.add_record_changes(record)

        _zone.commit()
