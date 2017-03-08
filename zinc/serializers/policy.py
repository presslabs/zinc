from rest_framework import serializers
from zinc.models import Policy, PolicyMember


class PolicyMemberSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)

    class Meta:
        model = PolicyMember
        fields = ['id', 'region', 'ip', 'weight']


class PolicySerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.CharField(read_only=True)
    members = PolicyMemberSerializer(many=True)

    class Meta:
        model = Policy
        fields = ['id', 'name', 'members', 'url']
