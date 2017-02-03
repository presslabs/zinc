from rest_framework.serializers import (HyperlinkedModelSerializer, ValidationError)
from rest_framework.fields import DictField

from dns.models import Zone
from dns.serializers import RecordSerializer
from dns.utils import route53


class ZoneListSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Zone
        fields = ['root', 'url', 'id']

    def create(self, validated_data):
        root = validated_data['root']
        if not root.endswith('.'):
            validated_data['root'] += '.'

        try:
            zone = route53.Zone.create(validated_data['root'])
        except route53.ClientError as e:
            raise ValidationError(detail=str(e))

        return Zone.objects.create(route53_id=zone.id,
                                   caller_reference=zone.caller_reference,
                                   **validated_data)


class ZoneDetailSerializer(HyperlinkedModelSerializer):
    records = DictField(child=RecordSerializer(partial=False))

    class Meta:
        model = Zone
        fields = ['root', 'url', 'records']
        read_only_fields = ['root', 'url']

    def __init__(self, *args, **kwargs):
        super(ZoneDetailSerializer, self).__init__(*args, **kwargs)
        self.partial = False

    def update(self, instance, validated_data):
        validated_records = validated_data['records']
        for record_hash, record in instance.records.items():
            if (record_hash in validated_data['records'] and
                (record['name'] != validated_records[record_hash]['name'] or
                 record['type'] != validated_records[record_hash]['type'])):
                record['delete'] = True
                validated_records.update({record_hash: record,
                                          'new': validated_records[record_hash]})

        instance.records = validated_records
        instance.save()
        return instance
