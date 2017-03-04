from contextlib import contextmanager

from rest_framework import fields
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from botocore.exceptions import ClientError

from dns.models import RECORD_PREFIX
from zinc import ZINC_RECORD_TYPES, POLICY_ROUTED
from zinc.vendors import hashids
from zinc import ALLOWED_RECORD_TYPES


@contextmanager
def interpret_client_error():
    try:
        yield
    except ClientError as error:
        if 'ARRDATAIllegalIPv4Address' in error.response['Error']['Message']:
            raise ValidationError({'values': ["Value is not a valid IPv4 address."]})
        elif 'AAAARRDATAIllegalIPv6Address' in error.response['Error']['Message']:
            raise ValidationError({'values': ["Value is not a valid IPv6 address."]})
        raise ValidationError({'non_field_error': [error.response['Error']['Message']]})


class RecordListSerializer(serializers.ListSerializer):
    # This is ued for list the records in Zone serializer
    # by using many=True and passing the entier zone as object

    def to_representation(self, zone):
        # pass to RecordSerializer zone in the context.
        self.context['zone'] = zone

        # return all zone records
        records = zone.records
        for record in records:
            record['zone'] = zone

        return super(RecordListSerializer, self).to_representation(records)

    def update(self, instnace, validated_data):
        raise NotImplementedError('Can not update records this way. Use records/ endpoint.')


class RecordSerializer(serializers.Serializer):
    name = fields.CharField(max_length=255)
    type = fields.ChoiceField(choices=ZINC_RECORD_TYPES)
    values = fields.ListField(child=fields.CharField())
    ttl = fields.IntegerField(allow_null=True, min_value=1, required=False)
    dirty = fields.SerializerMethodField(required=False)
    id = fields.SerializerMethodField(required=False)
    url = fields.SerializerMethodField(required=False)
    managed = fields.SerializerMethodField(required=False)

    class Meta:
        list_serializer_class = RecordListSerializer

    def get_id(self, obj):
        return hashids.encode_record(obj, self.context['zone'].route53_zone.id)

    def get_url(self, obj):
        # compute the url for record
        zone = self.context['zone']
        request = self.context['request']
        record_id = self.get_id(obj)
        return request.build_absolute_uri('/zones/%s/records/%s' % (zone.id, record_id))

    def get_managed(self, obj):
        return obj.get('managed', False)

    def get_dirty(self, obj):
        return obj.get('dirty', False)

    def create(self, validated_data):
        zone = self.context['zone']
        validated_data['id'] = self.get_id(validated_data)
        record = zone.add_record(validated_data)
        with interpret_client_error():
            zone.save()
        return record

    def update(self, obj, validated_data):
        zone = self.context['zone']
        obj.update(validated_data)
        if obj.get('managed'):
            raise ValidationError("Can't {} a managed record.".format(
                self.context['request'].method
            ))
        record = zone.add_record(obj)
        with interpret_client_error():
            zone.save()
        return record

    def validate_type(self, value):
        if value not in ALLOWED_RECORD_TYPES:
            raise ValidationError("Type '{}' is not allowed.".format(value))
        return value

    def validate_name(self, value):
        # record name should not start with rezerved prefix.
        if value.startswith(RECORD_PREFIX):
            raise ValidationError(
                ('Record {} can\'t start with {}. '
                 'It\'s a reserved prefix.').format(value, RECORD_PREFIX)
            )
        return value

    def validate(self, data):
        # if is a delete then the data should be {'delete': True}
        if self.context['request'].method == 'DELETE':
            return {'delete': True}

        # for PATCH type and name field can't be modified.
        if self.context['request'].method == 'PATCH':
            if 'type' in data or 'name' in data:
                raise ValidationError("Can't update 'name' and 'type' fields. ")
            return data

        # for POLICY_ROUTED the values should contain just one value
        if data['type'] == POLICY_ROUTED:
            if not len(data['values']) == 1:
                raise ValidationError({'values': ('For POLICY_ROUTED record values list '
                                                  'should contain just one element.')})
            return data

        # for normal records ttl and values fields are required.
        if not data.get('ttl', False):
            raise ValidationError({'ttl': 'This field is required for {} '
                                   'records.'.format(data.get('type'))})
        if not data.get('values', False):
            raise ValidationError({'values': 'This field is required.'})

        return data
