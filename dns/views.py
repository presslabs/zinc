from rest_framework.generics import (CreateAPIView, RetrieveUpdateDestroyAPIView)
from rest_framework import viewsets, status, mixins
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.exceptions import NotFound

from dns.serializers import (PolicySerializer, ZoneDetailSerializer,
                             ZoneListSerializer, RecordSerializer)
from dns import models


class PolicyViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = PolicySerializer
    queryset = models.Policy.objects.all()


class ZoneViewset(mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin,
                  mixins.ListModelMixin,
                  viewsets.GenericViewSet):
    queryset = models.Zone.objects.filter(deleted=False)

    def get_serializer_class(self):
        if self.action in ['list', 'create']:
            return ZoneListSerializer
        return ZoneDetailSerializer

    def destroy(self, request, pk=None):
        zone = get_object_or_404(models.Zone.objects, pk=pk)
        zone.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecordDetail(RetrieveUpdateDestroyAPIView):
    queryset = models.Zone.objects.filter(deleted=False)
    serializer_class = RecordSerializer

    @property
    def allowed_methods(self):
        _allowed_methods = self._allowed_methods()
        _allowed_methods.pop(_allowed_methods.index('PUT'))
        return _allowed_methods

    def get_object(self):
        queryset = self.get_queryset()
        zone = get_object_or_404(queryset, id=self.kwargs['zone_id'])

        for record in zone.records:
            if record['id'] == self.kwargs['record_id']:
                return record
        raise NotFound(detail='Record not found.')

    def get_zone(self):
        zone_id = self.kwargs.get('zone_id')
        if zone_id is not None:
            return get_object_or_404(models.Zone, id=zone_id)

    def get_serializer_context(self):
        zone = self.get_zone()
        context = super(RecordDetail, self).get_serializer_context()
        context['zone'] = zone
        return context

    def perform_destroy(self, instance):
        serializer = self.get_serializer(instance, data={}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()


class RecordCreate(CreateAPIView):
    serializer_class = RecordSerializer

    def get_queryset(self):
        return None

    def get_object(self):
        zone_id = self.kwargs.get('zone_id')
        if zone_id is not None:
            return get_object_or_404(models.Zone, id=zone_id)

    def get_serializer_context(self):
        zone = self.get_object()
        context = super(RecordCreate, self).get_serializer_context()
        context['zone'] = zone
        return context
