from django.contrib import admin
from django.db import transaction

from zinc.models import PolicyRecord
from zinc.admin.zone import aws_zone_link
from zinc.admin.soft_delete import SoftDeleteAdmin


@admin.register(PolicyRecord)
class PolicyRecordAdmin(SoftDeleteAdmin):
    list_display = ('__str__', 'aws_link', 'synced', 'is_deleted')
    list_filter = ('zone', 'policy', 'dirty')

    fields = ('name', 'zone', 'policy', 'synced',)
    readonly_fields = ('synced', )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('name',)
        return self.readonly_fields

    def synced(self, obj):
        return not obj.dirty
    synced.boolean = True
    synced.short_description = 'Synced'
    synced.admin_order_field = 'dirty'

    def aws_link(self, obj):
        return aws_zone_link(obj.zone.route53_id) if obj.zone.route53_id else ""
    aws_link.allow_tags = True
    aws_link.short_description = 'Zone'
    aws_link.admin_order_field = 'zone'

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if form.changed_data:
            obj.dirty = True
        super().save_model(request, obj, form, change)
