from rest_framework import serializers

from dns.models import PolicyMember


class PolicyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PolicyMember
        fields = ('location', 'ip', 'weight')
