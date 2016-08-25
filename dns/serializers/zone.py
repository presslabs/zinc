import hashlib
import random
import string
import time
from rest_framework import serializers

from dns.models import Zone
from zinc.vendors.boto3 import client


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = ['id', 'root', 'route53_id']
        read_only_fields = ['route53_id']


class ZoneDetailSerializer(serializers.ModelSerializer):
    ns = serializers.SerializerMethodField()
    records = serializers.SerializerMethodField()

    def get_ns(self, obj):
        return []

    def create(self, validated_data):
        ref_hash = bytes('{}{}{}{}'.format(
            time.time(),
            random.choice(string.ascii_letters),
            random.choice(string.ascii_letters),
            random.choice(string.ascii_letters),
        ), 'utf-8')
        response = client.create_hosted_zone(
            Name=validated_data['name'],
            CallerReference=hashlib.sha224(ref_hash).hexdigest()
        )
        validated_data['route53_id'] = response['HostedZone']['Id']
        return super(ZoneSerializer, self).create(validated_data)

    class Meta:
        model = Zone
        fields = ['id', 'root', 'route53_id', 'ns', 'records']
        read_only_fields = ['route53_id']
