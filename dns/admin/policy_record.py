from django.contrib import admin

from dns.models import PolicyRecord


@admin.register(PolicyRecord)
class PolicyRecordAdmin(admin.ModelAdmin):
    pass
