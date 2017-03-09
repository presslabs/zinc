from django.contrib import admin

from zinc.models import PolicyRecord
from zinc.admin.zone import aws_zone_link
from zinc.admin.soft_delete import SoftDeleteAdmin


@admin.register(PolicyRecord)
class PolicyRecordAdmin(SoftDeleteAdmin):
    list_display = ('__str__', 'aws_link', 'in_sync', 'is_deleted')
    list_filter = ('zone', 'policy', 'dirty')

    fields = ('name', 'zone', 'policy', 'in_sync',)
    readonly_fields = ('in_sync',)

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('name',)
        return self.readonly_fields

    def in_sync(self, obj):
        return not obj.dirty
    in_sync.boolean = True
    in_sync.short_description = 'In Sync'
    in_sync.admin_order_field = 'dirty'

    def aws_link(self, obj):
        return aws_zone_link(obj.zone.route53_id) if obj.zone.route53_id else ""
    aws_link.allow_tags = True
    aws_link.short_description = 'Zone'
    aws_link.admin_order_field = 'zone'
