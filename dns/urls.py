from django.conf.urls import url, include
from rest_framework import routers

from dns import views


router = routers.DefaultRouter()
router.register('policies', views.Policy, 'policy')

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^zones/$', views.ZoneList.as_view(), name='zone-list'),
    url(r'^zones/(?P<pk>[0-9]+)/?$',
        views.ZoneDetail.as_view(), name='zone-detail'),
    url(r'^zones/(?P<zone_id>[0-9]+)/records/(?P<record_id>\w+)/$',
        views.RecordDetail.as_view(), name='record-detail'),
    url(r'^zones/(?P<zone_id>[0-9]+)/records/$',
        views.RecordCreate.as_view(), name='record-create'),
    url(r'^policy-members/(?P<pk>[a-zA-Z0-9-]+)/$',
        views.PolicyMemberDetail.as_view(), name='policy-member-detail'),

]
