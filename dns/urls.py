from django.conf.urls import url

from .views import ZoneList, ZoneDetail


urlpatterns = [
    url(r'^$', ZoneList.as_view()),
    url(r'^(?P<zone_id>[0-9]+)', ZoneDetail.as_view())
]
