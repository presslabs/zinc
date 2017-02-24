from rest_framework import fields
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from dns.models import RECORD_PREFIX
from zinc import ZINC_RECORD_TYPES, POLICY_ROUTED
from zinc.vendors import hashids


class RecordListSerializer(serializers.ListSerializer):

    def to_representation(self, zone):
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
    ttl = fields.IntegerField(allow_null=True, min_value=300, required=False)
    dirty = fields.SerializerMethodField(required=False)
    id = fields.SerializerMethodField(required=False)
    url = fields.SerializerMethodField(required=False)
    managed = fields.SerializerMethodField(required=False)

    class Meta:
        list_serializer_class = RecordListSerializer

    def get_id(self, obj):
        return obj['id'] if 'id' in obj else hashids.encode_record(
            obj,
            self.context['zone'].route53_zone.id
        )

    def get_url(self, obj):
        zone = self.context.get('zone')
        zone_id = zone.id if zone else obj['zone_id']
        record_id = obj['id'] if 'id' in obj else hashids.encode_record(obj, zone.route53_zone.id)
        return '/zones/{}/records/{}/'.format(zone_id, record_id)

    def get_managed(self, obj):
        return obj.get('managed', False)

    def get_dirty(self, obj):
        return obj.get('dirty', False)

    def create(self, validated_data):
        zone = self.context['zone']
        validated_data['id'] = self.get_id(validated_data)
        record = zone.add_record(validated_data)
        zone.save()
        return record

    def update(self, obj, validated_data):
        zone = self.context['zone']
        obj.update(validated_data)
        record = zone.add_record(obj)
        zone.save()
        return record

    def validate_name(self, value):
        if value.startswith(RECORD_PREFIX):
            raise ValidationError(
                ('Record {} can\'t start with {}. '
                 'It\'s a reserved prefix.').format(value, RECORD_PREFIX)
            )
        return value

    def validate(self, data):
        if self.context['request'].method == 'DELETE':
            return {'delete': True}

        if self.context['request'].method == 'PATCH':
            if 'type' in data or 'name' in data:
                raise ValidationError('Can\'t update \'name\' and \'type\' fields. ')
            return data

        if data['type'] == POLICY_ROUTED:
            if not len(data['values']) == 1:
                raise ValidationError({'values': ('For POLICY_ROUTED record values list '
                                                  'should contain just one element.')})
            return data

        if not data.get('ttl', False):
            raise ValidationError({'ttl': ('This field is required. '
                                           'If record type is not POLICY_RECORD.')})
        if not data.get('values', False):
            raise ValidationError({'values': 'This field is required.'})

        return data
