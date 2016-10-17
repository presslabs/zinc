from django.conf.urls import url

from dns.views import RecordList, ZoneDetail, ZoneList


urlpatterns = [
    url(r'^$', ZoneList.as_view(), name='zones'),
    url(r'^(?P<pk>[0-9]+)/?$', ZoneDetail.as_view(), name='zones'),
    url(r'^(?P<pk>[0-9]+)/records/?$', RecordList.as_view(),
        name='zone-records')
]
