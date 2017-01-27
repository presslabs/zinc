from django.contrib import admin

from dns.models import Policy, PolicyMember


class PolicyMemberInline(admin.TabularInline):
    model = PolicyMember
    extra = 1
    verbose_name = 'member'
    verbose_name_plural = 'members'


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    inlines = [PolicyMemberInline]
    exclude = ['members']


admin.site.register(PolicyMember)

