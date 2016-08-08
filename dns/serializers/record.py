from rest_framework import serializers


class RecordSerializer(serializers.Serializer):
    RECORD_TYPES = [(type, type) for type in ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SPF', 'SRV', 'NS', 'SOA']]

    type = serializers.ChoiceField(choices=RECORD_TYPES)
    name = serializers.CharField(max_length=255)
    value = serializers.CharField()
    ttl = serializers.IntegerField(min_value=300)
    managed = serializers.BooleanField(default=False)
