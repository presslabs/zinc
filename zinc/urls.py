from django.conf.urls import url
from rest_framework import routers

from zinc import views


router = routers.DefaultRouter(trailing_slash=False)
router.register('policies', views.PolicyViewset, 'policy')
router.register('zones', views.ZoneViewset, 'zone')

urlpatterns = router.urls + [
    url(r'^zones/(?P<zone_id>[0-9]+)/records/(?P<record_id>\w+)$',
        views.RecordDetail.as_view(), name='record-detail'),
    url(r'^zones/(?P<zone_id>[0-9]+)/records$',
        views.RecordCreate.as_view(), name='record-create'),
]
