import logging

from botocore.exceptions import ClientError
from django.contrib import admin

from dns.models import IP


logger = logging.getLogger(__name__)


@admin.register(IP)
class IPAdmin(admin.ModelAdmin):
    list_display = ['ip', 'hostname', 'enabled']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            obj.reconcile_healthcheck()
        except ClientError:
            logger.exception("Error while calling reconcile_healthcheck")
