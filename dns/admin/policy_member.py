from django.contrib import admin

from dns.models import PolicyMember


@admin.register(PolicyMember)
class PolicyMemberAdmin(admin.ModelAdmin):
    pass
