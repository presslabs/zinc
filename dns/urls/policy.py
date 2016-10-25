from django.conf.urls import url

from dns.views import PolicyList, PolicyDetail


urlpatterns = [
    url(r'^$', PolicyList.as_view(), name='policy-list'),
    url(r'^(?P<pk>[0-9]+)/?$', PolicyDetail.as_view(), name='policy-detail')
]
