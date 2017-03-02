from django.contrib import admin


class SoftDeleteAdmin(admin.ModelAdmin):

    def get_actions(self, request):
        actions = super().get_actions(request)
        # we don't allow bulk delete of zones, because we want to enforce soft delete
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def delete_model(self, request, obj):
        """Soft delete zone object"""
        obj.soft_delete()

    def is_deleted(self, obj):
        return "DELETED" if obj.deleted else ""
