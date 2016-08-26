from django.contrib import admin

from dns.models import Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['root']
    readonly_fields = ['route53_id', 'caller_reference']

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields + ['root']
        return self.readonly_fields
