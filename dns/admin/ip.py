from django.contrib import admin

from dns.models import IP


@admin.register(IP)
class IPAdmin(admin.ModelAdmin):
    list_display = ['ip', 'hostname', 'enabled']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.reconcile_healthcheck()
