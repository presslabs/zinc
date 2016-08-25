from django.contrib import admin

from dns.models import Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['root']
    readonly_fields = ['route53_id']
