from contextlib import contextmanager

from rest_framework import fields
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from botocore.exceptions import ClientError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings

from zinc.models import RECORD_PREFIX
from zinc import route53
from zinc.route53.record import ZINC_RECORD_TYPES, POLICY_ROUTED, ALLOWED_RECORD_TYPES


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
    except DjangoValidationError as error:
        raise ValidationError(error.message_dict)


class RecordListSerializer(serializers.ListSerializer):
    # This is ued for list the records in Zone serializer
    # by using many=True and passing the entier zone as object

    def to_representation(self, zone):
        # pass to RecordSerializer zone in the context.
        self.context['zone'] = zone

        return super(RecordListSerializer, self).to_representation(zone.records)

    def update(self, instnace, validated_data):
        raise NotImplementedError('Can not update records this way. Use records/ endpoint.')


class RecordSerializer(serializers.Serializer):
    name = fields.CharField(max_length=255)
    fqdn = fields.SerializerMethodField(required=False)
    type = fields.ChoiceField(choices=ZINC_RECORD_TYPES)
    values = fields.ListField(child=fields.CharField())
    ttl = fields.IntegerField(allow_null=True, min_value=1, required=False)
    dirty = fields.SerializerMethodField(required=False)
    id = fields.SerializerMethodField(required=False)
    url = fields.SerializerMethodField(required=False)
    managed = fields.SerializerMethodField(required=False)

    class Meta:
        list_serializer_class = RecordListSerializer

    def get_fqdn(self, obj):
        zone = self.context['zone']
        if obj.name == '@':
            return zone.root
        return '{}.{}'.format(obj.name, zone.root)

    def get_id(self, obj):
        return obj.id

    def get_url(self, obj):
        # compute the url for record
        zone = self.context['zone']
        request = self.context['request']
        record_id = self.get_id(obj)
        return request.build_absolute_uri('/zones/%s/records/%s' % (zone.id, record_id))

    def get_managed(self, obj):
        return obj.managed

    def get_dirty(self, obj):
        return obj.dirty

    def to_representation(self, obj):
        assert obj.values if obj.is_alias else True
        rv = super().to_representation(obj)
        return rv

    def create(self, validated_data):
        zone = self.context['zone']
        obj = route53.record_factory(zone=zone, created=True, **validated_data)
        with interpret_client_error():
            obj.full_clean()
            obj.save()
            zone.r53_zone.commit()
        return obj

    def update(self, obj, validated_data):
        zone = self.context['zone']
        if obj.managed:
            raise ValidationError("Can't change a managed record.")
        for attr, value in validated_data.items():
            setattr(obj, attr, value)
        obj.full_clean()
        obj.save()
        with interpret_client_error():
            zone.commit()
        return obj

    def validate_type(self, value):
        if value not in ALLOWED_RECORD_TYPES:
            raise ValidationError("Type '{}' is not allowed.".format(value))
        return value

    def validate_name(self, value):
        # record name should not start with reserved prefix.
        if value.startswith(RECORD_PREFIX):
            raise ValidationError(
                ('Record {} can\'t start with {}. '
                 'It\'s a reserved prefix.').format(value, RECORD_PREFIX)
            )
        return value

    def validate(self, data):
        errors = {}
        # TODO: this stinks! we need a cleaner approach here
        # if is a delete then the data should be {'deleted': True}
        if self.context['request'].method == 'DELETE':
            return {'deleted': True}

        # for PATCH type and name field can't be modified.
        if self.context['request'].method == 'PATCH':
            if 'type' in data or 'name' in data:
                errors.update({'non_field_errors': ["Can't update 'name' and 'type' fields. "]})
        else:
            # POST method
            # for POLICY_ROUTED the values should contain just one value
            if data['type'] in ['CNAME', POLICY_ROUTED]:
                if not len(data['values']) == 1:
                    errors.update({
                        'values': ('Only one value can be '
                                   'specified for {} records.'.format(data['type']))
                    })
            else:
                data.setdefault('ttl', settings.ZINC_DEFAULT_TTL)
                # for normal records values is required.
                if not data.get('values', False):
                    errors.update({'values': 'This field is required.'})

        if errors:
            raise ValidationError(errors)

        return data
