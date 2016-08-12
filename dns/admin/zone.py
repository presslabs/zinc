from django.contrib import admin

from ..models import Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['root']
    readonly_fields = ['aws_id']
