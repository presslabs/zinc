from django.conf.urls import url

from dns.views import PolicyList, PolicyDetail


urlpatterns = [
    url(r'^$', PolicyList.as_view()),
    url(r'^(?P<pk>[0-9]+)', PolicyDetail.as_view())
]
