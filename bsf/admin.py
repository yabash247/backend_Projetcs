from django.contrib import admin
from .models import StaffMember, Farm

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'name', 'description', 'established_date', 'location', 'contact_number', 'email', 'website', 'status', 'created_at', 'updated_at')

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('id','user', 'position', 'farm', 'company', 'level', 'status', 'assigned_at', 'created_by')
    search_fields = ('user__username', 'farm__name', 'position')
    list_filter = ('position', 'level', 'status', 'farm', 'assigned_at')
    list_editable = ('position', 'level', 'status')
