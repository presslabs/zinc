from django.contrib import admin

from ..models import Policy


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    pass

