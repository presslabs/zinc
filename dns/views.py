from django.shortcuts import get_object_or_404
from rest_framework import generics

from dns.models import Policy, PolicyMember, Zone
from dns.serializers import (PolicySerializer, PolicyMemberSerializer,
                             RecordSerializer, ZoneSerializer,
                             ZoneDetailSerializer)
from dns.utils import route53


class ZoneList(generics.ListCreateAPIView):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer


class ZoneDetail(generics.RetrieveDestroyAPIView):
    queryset = Zone.objects.all()
    serializer_class = ZoneDetailSerializer


class PolicyList(generics.ListAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer


class PolicyDetail(generics.RetrieveUpdateAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer


class PolicyMemberDetail(generics.RetrieveAPIView):
    queryset = PolicyMember.objects.all()
    serializer_class = PolicyMemberSerializer


class RecordList(generics.UpdateAPIView, generics.ListAPIView):
    serializer_class = RecordSerializer

    def get_queryset(self):
        zone = get_object_or_404(Zone, pk=self.kwargs['pk'])
        route53_zone = route53.Zone(zone.route53_id, zone.root)

        records = route53_zone.records
        records.append(route53_zone.ns)

        return records

    def update(self):
        pass
