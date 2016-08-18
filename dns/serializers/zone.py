from rest_framework import serializers

from . import RecordSerializer
from ..models import Zone


class ZoneSerializer(serializers.ModelSerializer):
    records = RecordSerializer(many=True, read_only=True)

    class Meta:
        model = Zone
        fields = ('name', 'root', 'policy', 'aws_id', 'records')
        read_only_fields = ('aws_id', 'records')
