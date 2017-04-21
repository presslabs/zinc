import logging

from botocore.exceptions import ClientError
from django.contrib import admin

from zinc.models import Zone

from .soft_delete import SoftDeleteAdmin

logger = logging.getLogger('zinc.admin')


def aws_zone_link(r53_zone_id):
    return ('<a href="https://console.aws.amazon.com/route53/home?region=us-east-1'
            '#resource-record-sets:{0}">AWS:{0}</a>'.format(r53_zone_id))


@admin.register(Zone)
class ZoneAdmin(SoftDeleteAdmin):
    list_filter = ('ns_propagated', 'deleted')
    list_display = ('root', 'aws_link', 'ns_propagated', 'is_deleted')
    fields = ('root', 'route53_id', 'caller_reference', 'ns_propagated')
    readonly_fields = ('route53_id', 'caller_reference', 'ns_propagated')
    search_fields = ('root', 'route53_id')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ('root',)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        try:
            obj.reconcile()
        except ClientError:
            logger.exception("Error while calling reconcile for hosted zone")

    def aws_link(self, obj):
        return aws_zone_link(obj.route53_id) if obj.route53_id else ""
    aws_link.allow_tags = True
    aws_link.short_description = 'Zone'
    aws_link.admin_order_field = 'zone'
