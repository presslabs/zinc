from rest_framework import generics

from .models import ManagedRecord, Policy, Zone
from .serializers import PolicySerializer, RecordSerializer, ZoneSerializer


class ZoneList(generics.ListCreateAPIView):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer


class ZoneDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ZoneSerializer

    def get_queryset(self):
        return Zone.objects.filter(id=self.kwargs['pk'])


class PolicyList(generics.ListCreateAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer


class PolicyDetail(generics.RetrieveUpdateAPIView):
    serializer_class = PolicySerializer

    def get_queryset(self):
        return Policy.objects.filter(id=self.kwargs['pk'])


class RecordList(generics.ListCreateAPIView):
    queryset = ManagedRecord.objects.all()
    serializer_class = RecordSerializer
