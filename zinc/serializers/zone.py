from django.db import transaction
from rest_framework import serializers
from rest_framework.reverse import reverse

from zinc.models import Zone
from zinc.serializers import RecordSerializer
from zinc import route53


class ZoneListSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Zone
        fields = ['root', 'url', 'id', 'route53_id', 'dirty', 'ns_propagated']
        read_only_fields = ['dirty', 'ns_propagated']

    @transaction.atomic
    def create(self, validated_data):
        zone = Zone.objects.create(**validated_data)
        zone.full_clean()
        try:
            zone.route53_zone.create()
        except route53.ClientError as e:
            raise serializers.ValidationError(detail=str(e))
        return zone


class ZoneDetailSerializer(serializers.HyperlinkedModelSerializer):
    records = RecordSerializer(many=True, source='*')
    records_url = serializers.SerializerMethodField()

    def get_records_url(self, obj):
        request = self.context.get('request')
        return reverse('record-create', request=request,
                       kwargs={
                           'zone_id': obj.pk
                       })

    class Meta:
        model = Zone
        fields = ['root', 'url', 'records_url', 'records', 'route53_id', 'dirty', 'ns_propagated']
        read_only_fields = ['root', 'url', 'route53_id', 'dirty', 'ns_propagated']

    def __init__(self, *args, **kwargs):
        super(ZoneDetailSerializer, self).__init__(*args, **kwargs)
        self.partial = False
