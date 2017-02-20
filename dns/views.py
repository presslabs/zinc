from django.shortcuts import get_object_or_404
from rest_framework.generics import (CreateAPIView, ListCreateAPIView,
                                     RetrieveAPIView, RetrieveUpdateDestroyAPIView,
                                     ListAPIView)
from rest_framework import viewsets
from rest_framework import status
from rest_framework.response import Response

from dns import models
from dns import tasks
from dns.parsers import JSONMergePatchParser
from dns.serializers import (PolicySerializer, PolicyMemberSerializer,
                             ZoneDetailSerializer, ZoneListSerializer)


class ZoneList(ListCreateAPIView):
    queryset = models.Zone.objects.filter(deleted=False)
    serializer_class = ZoneListSerializer


class ZoneDetail(CreateAPIView, RetrieveUpdateDestroyAPIView):
    parser_classes = (JSONMergePatchParser,)
    queryset = models.Zone.objects.filter(deleted=False)
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


class Policy(viewsets.ModelViewSet):
    serializer_class = PolicySerializer
    queryset = models.Policy.objects.all()


class PolicyMemberDetail(RetrieveAPIView):
    queryset = models.PolicyMember.objects.all()
    serializer_class = PolicyMemberSerializer
