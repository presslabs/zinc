from django.shortcuts import get_object_or_404
from rest_framework import generics

from dns.models import Policy, Zone
from dns.serializers import (PolicySerializer, RecordSerializer,
                             ZoneSerializer, ZoneDetailSerializer)
from dns.utils import route53


class ZoneList(generics.ListCreateAPIView):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer


class ZoneDetail(generics.RetrieveUpdateDestroyAPIView):
    lookup_url_kwarg = 'zone_id'
    serializer_class = ZoneDetailSerializer

    def get_queryset(self):
        return Zone.objects.filter(id=self.kwargs['zone_id'])


class PolicyList(generics.ListCreateAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer


class PolicyDetail(generics.RetrieveUpdateAPIView):
    serializer_class = PolicySerializer

    def get_queryset(self):
        return Policy.objects.filter(id=self.kwargs['pk'])


class RecordList(generics.UpdateAPIView, generics.ListAPIView):
    lookup_field = 'zone_id'
    serializer_class = RecordSerializer

    def get_queryset(self):
        zone = get_object_or_404(Zone, pk=self.kwargs['zone_id'])
        route53_zone = route53.Zone(zone.route53_id, zone.root)

        records = route53_zone.records
        records.append(route53_zone.ns)

        return records
