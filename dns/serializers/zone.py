from rest_framework import serializers

from . import RecordSerializer
from ..models import Zone


class ZoneSerializer(serializers.Serializer):
    records = RecordSerializer(many=True)

    class Meta:
        model = Zone
        fields = ('name', 'root', 'policy', 'aws_id')
        read_only_fields = ('aws_id')
