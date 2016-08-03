from django.contrib import admin
from .models import Zone


class ZoneAdmin(admin.ModelAdmin):
    pass
admin.site.register(Zone, ZoneAdmin)
