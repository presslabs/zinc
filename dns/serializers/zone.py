from rest_framework.serializers import (HyperlinkedModelSerializer, ValidationError)

from dns.models import Zone
from dns.serializers import RecordSetSerializer
from dns.utils import route53


class ZoneListSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Zone
        fields = ['root', 'url', 'id']

    def create(self, validated_data):
        try:
            zone = route53.Zone.create(validated_data.get('root', ''))
        except route53.ClientError as e:
            raise ValidationError(detail=str(e))

        return Zone.objects.create(route53_id=zone.id,
                                   caller_reference=zone.caller_reference,
                                   **validated_data)


class ZoneDetailSerializer(HyperlinkedModelSerializer):
    records = RecordSetSerializer()

    class Meta:
        model = Zone
        fields = ['root', 'url', 'records']
        read_only_fields = ['root', 'url']

    def __init__(self, *args, **kwargs):
        super(ZoneDetailSerializer, self).__init__(*args, **kwargs)
        self.partial = False

    def update(self, instance, validated_data):

        instance.records = validated_data['records']

        return instance
