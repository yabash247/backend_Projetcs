from django.contrib import admin
from .models import Company, Staff, Authority, Branch, Media, Task

@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    list_display = ('app_name', 'model_name', 'company', 'requested_by', 'approver', 'created')
    list_filter = ('company', 'created')  # Filter by company and created date
    search_fields = ('model_name', 'company__name', 'requested_by__username', 'approver__username')  # Searchable fields

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'phone', 'status', 'created_date')  # Fields displayed in admin list
    list_filter = ('status', 'created_date')  # Filter options for status and created date
    search_fields = ('name', 'email')  # Searchable fields
    ordering = ('-created_date',)  # Default ordering

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'company', 'salary', 'reward_factor', 'reward', 'work_email', 'work_phone', 'date_created', 'added_by', 'approved_by')
    list_filter = ('company', 'date_created')  # Filter by company and creation date
    search_fields = ('user__username', 'company__name', 'work_email')  # Enable search by user, company, or email
    list_editable = ('salary', 'reward_factor', 'reward')  # Editable fields
    ordering = ('-date_created',)  # Sort by newest first


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "branch_id", "status", "appName", "modelName", "created_at")
    search_fields = ("name", "company__name", "branch_id", "status", "appName", "modelName")
    list_filter = ("company", "status", "created_at", "appName", "modelName")



@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "company",
        "branch",
        "app_name",
        "model_name",
        "model_id",
        "status",
        "created_date",
        "uploaded_by",
    )
    list_filter = ("company", "branch", "app_name", "model_name", "status")
    search_fields = ("title", "app_name", "model_name")
    ordering = ("-created_date",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'assigned_to', 'assistant', 'status', 'due_date', 'completed_date', 'company', 'branch', 'title']
    list_filter = ['status', 'company', 'branch']
    list_editable = ['status', 'due_date', 'assigned_to', 'assistant', 'completed_date']
    search_fields = ['title', 'description']


from .models import ActivityOwner
@admin.register(ActivityOwner)
class ActivityOwnerAdmin(admin.ModelAdmin):
    list_display = ('id','company', 'branch', 'activity', 'owner', 'assistant', 'status', 'created_date')
    list_filter = ('status', 'created_date')
    search_fields = ('company', 'branch', 'activity')

from .models import ActivityDefaultSetting
@admin.register(ActivityDefaultSetting)
class ActivityDefaultSettingAdmin(admin.ModelAdmin):
    list_display = ('name', 'appName', 'modelName', 'min_count', 'min_duration')
    search_fields = ('name', 'appName', 'modelName')
    list_filter = ('appName', 'modelName')
    list_editable = ('min_count', 'min_duration')
    ordering = ('name',)

from .models import RewardsPointsTracker
@admin.register(RewardsPointsTracker)
class RewardsPointsTrackerAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'company', 'branch', 'task', 'credit', 'credit_date', 'debit', 'debit_date', 'points_available', 'points_pending', 'updated_at')
    search_fields = ('user__username', 'company__name', 'branch__name', 'task__title')
    list_filter = ('company', 'branch', 'credit_date', 'debit_date', 'updated_at')
    readonly_fields = ('points_available', 'points_pending', 'updated_at')
    list_editable = ('credit', 'debit')


from .models import Expectations
@admin.register(Expectations)
class ExpectationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'company',
        'branch',
        'app_name',
        'model_name',
        'model_rowName',
        'status',
        'quantity',
        'uom',
        'created_date',
        'created_by',
    )
    list_filter = ('company', 'branch', 'status', 'uom', 'created_date')
    search_fields = ('app_name', 'model_name', 'model_rowName', 'company__name', 'branch__name')
    ordering = ('-created_date',)
    readonly_fields = ('created_date', 'created_by')

    def save_model(self, request, obj, form, change):
        """
        Automatically sets the `created_by` field to the current user if it's not already set.
        """
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
