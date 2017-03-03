import logging

from botocore.exceptions import ClientError
from django.contrib import admin

from dns.models import Zone

from .soft_delete import SoftDeleteAdmin

logger = logging.getLogger('zinc.admin')


@admin.register(Zone)
class ZoneAdmin(SoftDeleteAdmin):
    list_display = ['root', 'is_deleted', 'aws_link']
    readonly_fields = ['route53_id', 'caller_reference']
    list_filter = ['deleted']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['root']
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            obj.reconcile()
        except ClientError:
            logger.exception("Error while calling reconcile for hosted zone")

    def aws_link(self, obj):
        if obj.route53_id is not None:
            return ('<a href="https://console.aws.amazon.com/route53/home?region=us-east-1'
                    '#resource-record-sets:{0}">AWS:{0}</a>'.format(obj.route53_id))
        else:
            return ""
    aws_link.allow_tags = True
