import json
from django.conf import settings
from rest_framework.generics import (CreateAPIView, ListAPIView, ListCreateAPIView,
                                     RetrieveAPIView, RetrieveUpdateAPIView,
                                     RetrieveUpdateDestroyAPIView)

from dns.models import Policy, PolicyMember, Zone
from dns.parsers import JSONMergePatchParser
from dns.serializers import (PolicySerializer, PolicyMemberSerializer,
                             ZoneDetailSerializer, ZoneListSerializer)
from dns.utils import route53
from dns.utils.generic import dict_key_intersection


class ZoneList(ListCreateAPIView):
    queryset = Zone.objects.all()
    serializer_class = ZoneListSerializer


class ZoneDetail(CreateAPIView, RetrieveUpdateDestroyAPIView):
    parser_classes = (JSONMergePatchParser,)
    queryset = Zone.objects.all()
    serializer_class = ZoneDetailSerializer

    @property
    def allowed_methods(self):
        _allowed_methods = self._allowed_methods()
        _allowed_methods.pop(_allowed_methods.index('PUT'))
        return _allowed_methods

    def initialize_request(self, request, *args, **kwargs):
        initial_request = super(ZoneDetail, self).initialize_request(request, *args, **kwargs)

        if initial_request.stream:
            parser_context = initial_request.parser_context.copy()

            zone_pk = parser_context['kwargs']['pk']
            root, route53_id = Zone.objects.values_list('root', 'route53_id').get(pk=zone_pk)
            zone = route53.Zone(id=route53_id, root=root)

            encoding = parser_context.get('encoding', settings.DEFAULT_CHARSET)

            body = initial_request.stream.body
            body = body.decode(encoding)

            try:
                body = json.loads(body)
                body = body.pop('records', {})
            except (TypeError, ValueError):
                body = {}

            '''
            In order to be JSON Merge Patch compliant, deleting a record
            will be done by sending a record key with the value `null`.

            E.g.: {"records": {"asd123qwerty": null}}

            However, to avoid trouble and too many diffs, this will be
            transformed into a key containing a `delete` flag with
            the value `true`. So the above record specified for deletion
            becomes {"records": {"asd123qwerty": {"delete": true}}}
            '''

            validated_body = body.copy()

            for key, value in body.items():
                if value is None:
                    validated_body[key] = {'delete': True}

            parser_context['kwargs']['input'] = {
                'records': dict_key_intersection(zone.records(), validated_body)
            }

            initial_request.parser_context = parser_context

        return initial_request

    def patch(self, request, *args, **kwargs):
        return super(ZoneDetail, self).patch(request, args, kwargs)


class PolicyList(ListAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer


class PolicyDetail(RetrieveUpdateAPIView):
    queryset = Policy.objects.all()
    serializer_class = PolicySerializer


class PolicyMemberDetail(RetrieveAPIView):
    queryset = PolicyMember.objects.all()
    serializer_class = PolicyMemberSerializer
