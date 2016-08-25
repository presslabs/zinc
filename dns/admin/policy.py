from django.contrib import admin

from dns.models import Policy


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    pass
