from django.http import HttpResponse
from rest_framework import generics

from .models.zone import Zone
from .serializers.zone import ZoneSerializer


class ZoneList(generics.ListCreateAPIView):
    serializer_class = ZoneSerializer

    def get_queryset(self):
        queryset = Zone.objects.all()
        return HttpResponse(queryset)
