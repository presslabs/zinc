from django.conf import settings
from django.conf.urls import url

from dns.views import PolicyMemberDetail

HASHIDS_MIN_LENGTH = getattr(settings, 'HASHIDS_MIN_LENGTH', 7)

urlpatterns = [
    url(r'^(?P<pk>[a-zA-Z0-9]{%d,%d})/?$' % (HASHIDS_MIN_LENGTH, HASHIDS_MIN_LENGTH),
        PolicyMemberDetail.as_view(), name='policymember-detail'),
]
