from rest_framework import serializers
from zinc.models import Policy, PolicyMember


class PolicyMemberSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    enabled = serializers.SerializerMethodField(read_only=True)

    def get_enabled(self, obj):
        return obj.enabled and obj.ip.enabled

    class Meta:
        model = PolicyMember
        fields = ['id', 'region', 'ip', 'weight', 'enabled']


class PolicySerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.CharField(read_only=True)
    members = PolicyMemberSerializer(many=True)

    class Meta:
        model = Policy
        fields = ['id', 'name', 'members', 'url']
