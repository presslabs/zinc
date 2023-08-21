from django.urls import path
from rest_framework import routers

from zinc import views


router = routers.DefaultRouter(trailing_slash=False)
router.register('policies', views.PolicyViewset, 'policy')
router.register('zones', views.ZoneViewset, 'zone')

urlpatterns = router.urls + [
    path('zones/<int:zone_id>/records/<str:record_id>',
        views.RecordDetail.as_view(), name='record-detail'),
    path('zones/<int:zone_id>/records',
        views.RecordCreate.as_view(), name='record-create'),
]
