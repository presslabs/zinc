import logging

from django.contrib import admin
from django.db import transaction

from zinc.models import IP

from .soft_delete import SoftDeleteAdmin


logger = logging.getLogger(__name__)


@admin.register(IP)
class IPAdmin(SoftDeleteAdmin):
    list_display = ('ip', 'hostname', 'enabled', 'healthcheck')
    list_filter = ('hostname', 'deleted')

    fields = ('ip', 'hostname', 'friendly_name', 'healthcheck_id',
              'healthcheck_caller_reference', 'enabled', 'deleted')

    readonly_fields = ('deleted',)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.reconcile_healthcheck()
        obj.mark_policy_records_dirty()

    def healthcheck(self, obj):
        if obj.healthcheck_id:
            return ('<a href="https://console.aws.amazon.com/route53/healthchecks/home'
                    '#/details/{0}">AWS:{0}</a>'.format(obj.healthcheck_id))
        else:
            return ""
    healthcheck.allow_tags = True
