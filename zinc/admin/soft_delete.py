from django.core.exceptions import PermissionDenied
from django.contrib import admin
from django.contrib.admin.actions import delete_selected as delete_selected_


def delete_selected(modeladmin, request, queryset):
    if not modeladmin.has_delete_permission(request):
        raise PermissionDenied
    if request.POST.get('post'):
        for obj in queryset:
            obj.soft_delete()
    else:
        return delete_selected_(modeladmin, request, queryset)
delete_selected.short_description = "Delete selected"  # noqa


class SoftDeleteAdmin(admin.ModelAdmin):
    actions = (delete_selected,)

    def delete_model(self, request, obj):
        """Soft delete zone object"""
        obj.soft_delete()

    def is_deleted(self, obj):
        return "DELETED" if obj.deleted else ""
