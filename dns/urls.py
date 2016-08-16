from django.conf.urls import url

from .views import ZoneList


urlpatterns = [
    url(r'.*', ZoneList.as_view()),
]
