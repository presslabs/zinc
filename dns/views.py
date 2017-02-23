from django.shortcuts import get_object_or_404
from rest_framework.generics import (CreateAPIView, ListCreateAPIView,
                                     RetrieveAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.exceptions import NotFound

from dns.serializers import (PolicySerializer, PolicyMemberSerializer,
                             ZoneDetailSerializer, ZoneListSerializer, RecordSerializer)
from dns.serializers import RecordListSerializer
from dns import models


class ZoneList(ListCreateAPIView):
    queryset = models.Zone.objects.filter(deleted=False)
    serializer_class = ZoneListSerializer


class ZoneDetail(CreateAPIView, RetrieveUpdateDestroyAPIView):
    queryset = models.Zone.objects.all()
    serializer_class = ZoneDetailSerializer

    @property
    def allowed_methods(self):
        _allowed_methods = self._allowed_methods()
        _allowed_methods.pop(_allowed_methods.index('PUT'))
        return _allowed_methods

    def post(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return super(ZoneDetail, self).patch(request, *args, **kwargs)

    def delete(self, request, pk, *args, **kwargs):
        zone = get_object_or_404(models.Zone.objects, pk=pk)
        zone.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecordDetail(RetrieveUpdateDestroyAPIView):
    queryset = models.Zone.objects.all()
    serializer_class = RecordSerializer

    def get_object(self):
        queryset = self.get_queryset()
        zone = get_object_or_404(queryset, id=self.kwargs['zone_id'])

        for record in zone.records:
            if record['id'] == self.kwargs['record_id']:
                return record
        raise NotFound(detail='Record not found.')

    def get_zone(self):
        return get_object_or_404(models.Zone, id=self.kwargs['zone_id'])

    def get_serializer_context(self):
        zone = self.get_zone()
        context = super(RecordDetail, self).get_serializer_context()
        context['zone'] = zone
        context['record_id'] = self.kwargs['record_id']
        return context

    def perform_destroy(self, instance):
        serializer = self.get_serializer(instance, data={}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()


class RecordCreate(CreateAPIView):
    serializer_class = RecordSerializer

    def get_object(self):
        return get_object_or_404(models.Zone, id=self.kwargs['zone_id'])

    def get_serializer_context(self):
        zone = self.get_object()
        context = super(RecordCreate, self).get_serializer_context()
        context['zone'] = zone
        return context


class Policy(viewsets.ModelViewSet):
    serializer_class = PolicySerializer
    queryset = models.Policy.objects.all()


class PolicyMemberDetail(RetrieveAPIView):
    queryset = models.PolicyMember.objects.all()
    serializer_class = PolicyMemberSerializer
