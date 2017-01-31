import json
from django.conf import settings
from rest_framework.generics import (CreateAPIView, ListAPIView, ListCreateAPIView,
                                     RetrieveAPIView, RetrieveUpdateAPIView,
                                     RetrieveUpdateDestroyAPIView)
from rest_framework import viewsets

from dns import models # import Policy, PolicyMember, Zone
from dns.parsers import JSONMergePatchParser
from dns.serializers import (PolicySerializer, PolicyMemberSerializer,
                             ZoneDetailSerializer, ZoneListSerializer)
from dns.utils import route53
from dns.utils.generic import dict_key_intersection


class ZoneList(ListCreateAPIView):
    queryset = models.Zone.objects.all()
    serializer_class = ZoneListSerializer


class ZoneDetail(CreateAPIView, RetrieveUpdateDestroyAPIView):
    parser_classes = (JSONMergePatchParser,)
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


class Policy(viewsets.ModelViewSet):
    serializer_class = PolicySerializer
    queryset = models.Policy.objects.all()


class PolicyMemberDetail(RetrieveAPIView):
    queryset = models.PolicyMember.objects.all()
    serializer_class = PolicyMemberSerializer
