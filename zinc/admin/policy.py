from django.contrib import admin
from django.db import transaction

from zinc.models import Policy, PolicyMember


class PolicyMemberInline(admin.TabularInline):
    readonly_fields = ('ip_enabled',)
    model = PolicyMember
    extra = 1
    verbose_name = 'member'
    verbose_name_plural = 'members'

    def ip_enabled(self, obj):
        return obj.ip.enabled
    ip_enabled.boolean = True


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    fields = ('name', 'routing',)
    readonly_fields = ()
    list_display = ('__str__', 'routing', 'regions', 'status')
    list_filter = ('routing', 'members__region')
    inlines = (PolicyMemberInline,)
    exclude = ('members',)

    def get_queryset(self, request):
        qs = super(PolicyAdmin, self).get_queryset(request)
        qs = qs.prefetch_related('members')
        return qs

    def regions(self, obj):
        # get_queryset prefetches related policy members so iterating over
        # objects is ok because we are iterating over already fetched data
        return ', '.join(sorted({m.region for m in obj.members.all()}))

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        rv = super().save_model(request, obj, form, change)
        obj.change_trigger(form.changed_data)
        return rv

    def status(self, obj):
        warnings = []
        if obj.routing == 'latency':
            members_by_region = {}
            for member in obj.members.all():
                members_by_region.setdefault(member.region, []).append(member)
            if len(members_by_region) <= 1:
                warnings.append('&#x2716; Latency routed policy should span multiple regions!')
            for region, members in members_by_region.items():
                if len([m for m in members if m.weight > 0]) == 0:
                    warnings.append(
                        '&#x2716; All members of region {} have weight zero!'.format(region))
        elif obj.routing == 'weighted':
            active_members = [m for m in obj.members.all() if m.weight > 0]
            if len(active_members) == 0:
                warnings.append('&#x2716; All members have weight zero!')
        if warnings:
            return '<span style="color: red">{}</red>'.format("<br>".join(warnings))
        else:
            return "&#x2714; ok"
    status.allow_tags = True
    status.short_description = 'Status'
