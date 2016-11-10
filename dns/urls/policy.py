from django.conf import settings
from django.conf.urls import url

from dns.views import PolicyList, PolicyDetail

HASHIDS_MIN_LENGTH = getattr(settings, 'HASHIDS_MIN_LENGTH', 7)

urlpatterns = [
    url(r'^$', PolicyList.as_view(), name='policy-list'),
    url(r'^(?P<pk>[a-zA-Z0-9]{%d,%d})/?$' % (HASHIDS_MIN_LENGTH, HASHIDS_MIN_LENGTH),
        PolicyDetail.as_view(), name='policy-detail'),
]
