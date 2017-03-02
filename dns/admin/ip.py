import logging

from botocore.exceptions import ClientError
from django.contrib import admin

from dns.models import IP

from .soft_delete import SoftDeleteAdmin


logger = logging.getLogger(__name__)


@admin.register(IP)
class IPAdmin(SoftDeleteAdmin):
    list_display = ['ip', 'hostname', 'enabled', 'healthcheck']
    list_filter = ['deleted']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            obj.reconcile_healthcheck()
        except ClientError:
            logger.exception("Error while calling reconcile_healthcheck")

    def healthcheck(self, obj):
        if obj.healthcheck_id is not None:
            return ('<a href="https://console.aws.amazon.com/route53/healthchecks/home'
                    '#/details/{0}">AWS:{0}</a>'.format(obj.healthcheck_id))
        else:
            return ""
    healthcheck.allow_tags = True
