from rest_framework import serializers

from dns.models import Zone
from dns.utils import route53


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = ['id', 'root']

    def create(self, validated_data):
        try:
            _zone = route53.Zone.create(validated_data['root'])
        except route53.ClientError as e:
            raise serializers.ValidationError(detail=str(e))

        return Zone.objects.create(route53_id=_zone.id,
                                   caller_reference=_zone.caller_reference,
                                   **validated_data)


class ZoneDetailSerializer(serializers.ModelSerializer):
    ns = serializers.SerializerMethodField()
    records = serializers.SerializerMethodField()

    def get_ns(self, obj):
        zone = route53.Zone(id=obj.route53_id, root=obj.root,
                            caller_reference=obj.caller_reference)
        return zone.ns

    def get_records(self, obj):
        zone = route53.Zone(id=obj.route53_id, root=obj.root,
                            caller_reference=obj.caller_reference)

        return zone.records

    class Meta:
        model = Zone
        fields = ['id', 'root', 'ns', 'records']
