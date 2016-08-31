from rest_framework import generics

from dns.models import PolicyRecord, Policy, Zone
from dns.serializers import (PolicySerializer, RecordSerializer,
                             ZoneSerializer, ZoneDetailSerializer)


class UpdateDestroyApiView(generics.CreateAPIView, generics.DestroyAPIView,
                           generics.UpdateAPIView):
    pass


class ZoneList(generics.ListCreateAPIView):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer


class ZoneDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ZoneDetailSerializer

    def get_queryset(self):
        return Zone.objects.filter(id=self.kwargs['pk'])


class PolicyList(generics.ListCreateAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer


class PolicyDetail(generics.RetrieveUpdateAPIView):
    serializer_class = PolicySerializer

    def get_queryset(self):
        return Policy.objects.filter(id=self.kwargs['pk'])


class RecordList(UpdateDestroyApiView):
    queryset = PolicyRecord.objects.all()
    serializer_class = RecordSerializer
