from django.conf.urls import url
from django.conf import settings

from dns.views import ZoneDetail, ZoneList

HASHIDS_MIN_LENGTH = getattr(settings, 'HASHIDS_MIN_LENGTH', 7)

urlpatterns = [
    url(r'^$', ZoneList.as_view(), name='zone-list'),
    url(r'^(?P<pk>[a-zA-Z0-9]{%d,%d})/?$' % (HASHIDS_MIN_LENGTH, HASHIDS_MIN_LENGTH),
        ZoneDetail.as_view(), name='zone-detail'),
]
