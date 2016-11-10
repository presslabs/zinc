from rest_framework.serializers import (HyperlinkedModelSerializer,
                                        HyperlinkedRelatedField, ModelSerializer)

from dns.models import Policy, PolicyMember


class PolicySerializer(HyperlinkedModelSerializer):
    members = HyperlinkedRelatedField(
        many=True,
        view_name='policymember-detail',
        queryset=PolicyMember.objects.all()
    )

    class Meta:
        model = Policy
        fields = ['name', 'members', 'url']


class PolicyMemberSerializer(ModelSerializer):
    class Meta:
        model = PolicyMember
        fields = ['location', 'ip', 'weight']
