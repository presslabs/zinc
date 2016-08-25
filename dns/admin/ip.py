from django.contrib import admin
from django.conf import settings

from ..models import IP


@admin.register(IP)
class IPAdmin(admin.ModelAdmin):
    list_display = ['ip', 'hostname', 'enabled']
    readonly_fields = []

    def get_readonly_fields(self, request, obj=None):
        fields = list(self.readonly_fields)
        if getattr(settings, 'DISABLE_IP_ADMIN', False):
            fields += [field.name for field in obj._meta.fields]

        return fields

    def has_add_permission(self, request):
        if getattr(settings, 'DISABLE_IP_ADMIN', False):
            return False

        return super(IPAdmin, self).has_add_permission(request=request)

    def has_delete_permission(self, request, obj=None):
        if getattr(settings, 'DISABLE_IP_ADMIN', False):
            return False

        return super(IPAdmin, self).has_delete_permission(request=request, obj=obj)

    def get_actions(self, request):
        actions = super(IPAdmin, self).get_actions(request)
        if getattr(settings, 'DISABLE_IP_ADMIN', False) and 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
