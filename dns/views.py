from django.shortcuts import get_object_or_404
from rest_framework import generics

from .models import Zone
from .serializers import ZoneSerializer


class ZoneList(generics.ListAPIView):
    queryset = Zone.objects.all()
    serializer_class = ZoneSerializer


class ZoneDetail(generics.GenericAPIView):
    serializer_class = ZoneSerializer

    def get_object(self, queryset=None):
        zone_id = self.kwargs['zone_id']
        zone = get_object_or_404(Zone, id=zone_id)
        return zone
