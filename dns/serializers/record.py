from rest_framework import serializers

from dns.models import PolicyRecord


class RecordSerializer(serializers.Serializer):
    RECORD_TYPES = [
        'A', 'AAAA', 'CNAME', 'MX', 'TXT',
        'SPF', 'SRV', 'NS', 'SOA', 'POLICY_ROUTED'
    ]

    name = serializers.CharField(max_length=255)
    record_type = serializers.ChoiceField(choices=[(rtype, rtype) for rtype in RECORD_TYPES])
    values = serializers.ListField()
    ttl = serializers.IntegerField(min_value=300)
    managed = serializers.BooleanField(default=False)
    dirty = serializers.BooleanField(default=False)

    class Meta:
        fields = ('name', 'record_type', 'values', 'ttl', 'managed', 'dirty')
        read_only_fields = ('managed', 'dirty')

    def create(self, validated_data):
        validated_data['dirty'] = True
        rtype = validated_data.pop('record_type')

        if rtype == 'POLICY_ROUTED':
            validated_data['managed'] = True
            PolicyRecord.objects.all().get_or_create(**validated_data)

        # TODO AWS stuff

    def update(self, instance, validated_data):
        rtype = validated_data.get('record_type')
        if rtype == 'POLICY_ROUTED':
            instance.save()

        # TODO AWS stuff
