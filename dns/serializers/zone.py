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
    _aws_records = []

    def _get_aws_records(self, obj):
        if self._aws_records:
            return
        else:
            response = route53.client.list_resource_record_sets(HostedZoneId=obj.route53_id)
            self._aws_records = response['ResourceRecordSets']

    def get_ns(self, obj):
        self._get_aws_records(obj)
        ns = {}
        root = '{}.'.format(obj.root) if not obj.root.endswith('.') else obj.root

        for record in self._aws_records:
            if record['Type'] == 'NS' and record['Name'] == root:
                ns = {
                    'name': record['Name'],
                    'type': record['Type'],
                    'ttl': record['TTL'],
                    'values': [r['Value'] for r in record['ResourceRecords']]
                }
            break
        return ns

    def get_records(self, obj):
        self._get_aws_records(obj)
        records = []
        root = '{}.'.format(obj.root) if not obj.root.endswith('.') else obj.root

        for record in self._aws_records:
            if not (record['Type'] == 'NS' and record['Name'] == root):
                records.append({
                    'name': record['Name'],
                    'type': record['Type'],
                    'ttl': record['TTL'],
                    'values': [r['Value'] for r in record['ResourceRecords']]
                })

        return records

    class Meta:
        model = Zone
        fields = ['id', 'root', 'ns', 'records']
