from rest_framework import serializers
from dns.models import Policy, PolicyMember


class PolicySerializer(serializers.HyperlinkedModelSerializer):
    id = serializers.CharField(read_only=True)
    members = serializers.HyperlinkedRelatedField(
        many=True,
        view_name='policymember-detail',
        queryset=PolicyMember.objects.all()
    )

    class Meta:
        model = Policy
        fields = ['id', 'name', 'members', 'url']


class PolicyMemberSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    class Meta:
        model = PolicyMember
        fields = ['id', 'location', 'ip', 'weight']
