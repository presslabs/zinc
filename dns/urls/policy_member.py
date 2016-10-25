from django.conf.urls import url

from dns.views import PolicyMemberDetail


urlpatterns = [
    url(r'^(?P<pk>[0-9]+)/?$', PolicyMemberDetail.as_view(),
        name='policymember-detail'),
]
