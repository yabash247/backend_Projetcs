from django.contrib import admin
from .models import StaffMember

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'position', 'farm', 'level', 'status', 'assigned_at', 'created_by')
    search_fields = ('user__username', 'farm__name', 'position')
    list_filter = ('position', 'level', 'status', 'farm', 'assigned_at')
