from django.contrib import admin
from .models import Company, Staff, Authority

@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    list_display = ('model_name', 'company', 'requested_by', 'approver', 'created')
    list_filter = ('company', 'created')  # Filter by company and created date
    search_fields = ('model_name', 'company__name', 'requested_by__username', 'approver__username')  # Searchable fields

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'status', 'created_date')  # Fields displayed in admin list
    list_filter = ('status', 'created_date')  # Filter options for status and created date
    search_fields = ('name', 'email')  # Searchable fields
    ordering = ('-created_date',)  # Default ordering

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'work_email', 'work_phone', 'date_created', 'added_by', 'approved_by')
    list_filter = ('company', 'date_created')  # Filter by company and creation date
    search_fields = ('user__username', 'company__name', 'work_email')  # Enable search by user, company, or email
    ordering = ('-date_created',)  # Sort by newest first