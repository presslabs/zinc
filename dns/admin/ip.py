from django.contrib import admin

from dns.models import IP


@admin.register(IP)
class IPAdmin(admin.ModelAdmin):
    list_display = ['ip', 'hostname', 'enabled']
