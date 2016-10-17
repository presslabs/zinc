from rest_framework import serializers

from dns.models import Policy, PolicyMember


class PolicySerializer(serializers.HyperlinkedModelSerializer):
    members = serializers.HyperlinkedRelatedField(
        many=True,
        view_name='policymember-detail',
        queryset=PolicyMember.objects.all()
    )

    class Meta:
        model = Policy
        fields = ('name', 'members', 'url')
