from rest_framework import serializers


class RecordSerializer(serializers.Serializer):
    RECORD_TYPES = [(rtype, rtype) for rtype in ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'SPF', 'SRV', 'NS', 'SOA']]

    record_type = serializers.ChoiceField(choices=RECORD_TYPES)
    name = serializers.CharField(max_length=255)
    value = serializers.CharField()
    ttl = serializers.IntegerField(min_value=300)
    managed = serializers.BooleanField(default=False)
