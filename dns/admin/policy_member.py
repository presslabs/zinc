from django.contrib import admin

from ..models import PolicyMember


@admin.register(PolicyMember)
class PolicyMemberAdmin(admin.ModelAdmin):
    pass
