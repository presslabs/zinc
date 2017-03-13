from django.contrib import admin
from django.db.models import Count, Case, When, Value, CharField

from zinc.models import Policy, PolicyMember


class PolicyMemberInline(admin.TabularInline):
    model = PolicyMember
    extra = 1
    verbose_name = 'member'
    verbose_name_plural = 'members'


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    fields = ('name', 'policy_type',)
    readonly_fields = ('policy_type',)
    list_display = ('__str__', 'policy_type', 'regions',)
    inlines = (PolicyMemberInline,)
    exclude = ('members',)

    def get_queryset(self, request):
        qs = super(PolicyAdmin, self).get_queryset(request)
        qs = qs.annotate(region_count=Count('members__region',
                                            distinct=True))
        qs = qs.annotate(
            region_count=Count(
                'members__region',
                distinct=True
            ),
            policy_type=Case(
                When(region_count=1, then=Value('weigthed')),
                When(region_count__gt=1, then=Value('lbr')),
                output_field=CharField()
            )
        )
        qs = qs.prefetch_related('members')
        return qs

    def policy_type(self, obj):
        return obj.policy_type
    policy_type.admin_order_field = 'policy_type'

    def regions(self, obj):
        # get_queryset prefetches related policy members so iterating over
        # objects is ok because we are iterating over already fetched data
        return ', '.join(sorted({m.region for m in obj.members.all()}))
