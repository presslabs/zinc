from django.contrib import admin

from dns.models import Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['root', 'is_deleted', 'aws_link']
    readonly_fields = ['route53_id', 'caller_reference']
    list_filter = ['deleted']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['root']
        return self.readonly_fields

    def get_actions(self, request):
        actions = super().get_actions(request)
        # we don't allow bulk delete of zones, because we want to enforce soft delete
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def delete_model(self, request, obj):
        """Soft delete zone object"""
        obj.soft_delete()

    def is_deleted(self, obj):
        return "DELETED" if obj.deleted else ""

    def aws_link(self, obj):
        if obj.route53_id is not None:
            return ('<a href="https://console.aws.amazon.com/route53/home?region=us-east-1'
                    '#resource-record-sets:{0}">AWS:{0}</a>'.format(obj.route53_id))
        else:
            return ""
    aws_link.allow_tags = True
