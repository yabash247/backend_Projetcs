from django.contrib import admin
from .models import StaffMember, Farm, Net, Batch, DurationSettings, Pond, NetUseStats, PondUseStats

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'name', 'description', 'established_date', 'location', 'contact_number', 'email', 'website', 'status', 'created_at', 'updated_at')

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('id','user', 'position', 'farm', 'company', 'level', 'status', 'assigned_at', 'created_by')
    search_fields = ('user__username', 'farm__name', 'position')
    list_filter = ('position', 'level', 'status', 'farm', 'assigned_at')
    list_editable = ('position', 'level', 'status')



@admin.register(Net)
class NetAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Net model.
    """
    list_display = ('id', 'name', 'farm', 'company', 'status', 'length', 'width', 'height', 'created_at')
    list_filter = ('status', 'company', 'farm')
    search_fields = ('name', 'farm__name', 'company__name')
    ordering = ('-created_at',)
        
    def get_readonly_fields(self, request, obj=None):
        """
        Return a list or tuple of field names that will be displayed as read-only in the admin interface.
        """
        if obj:
            return ('name', 'farm', 'company', 'created_at')
        return ()

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "batch_name",
        "farm",
        "company",
        "laying_status",
        "incubation_status",
        "nursery_status",
        "growout_status",
        "puppa_status",
        "created_at",
    )
    list_filter = ("farm", "company", "laying_status", "incubation_status", "nursery_status", "growout_status", "puppa_status")
    search_fields = ("batch_name", "farm__name", "company__name")
    ordering = ("-created_at",)
    readonly_fields = ("batch_name", "created_at")


@admin.register(DurationSettings)
class DurationSettingsAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "farm", "laying_duration", "nursery_duration", "incubation_duration"]
    search_fields = ["company__name", "farm__name"]


@admin.register(NetUseStats)
class NetUseStatsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "company",
        "farm",
        "net",
        "batch",
        "lay_start",
        "lay_end",
        "harvest_weight",
        "stats",
        "created_by",
        "approved_by",
        "created_at",
        "updated_at",
    )
    list_filter = ("stats", "created_at", "updated_at", "company", "farm")
    search_fields = (
        "net__name",
        "batch__batch_name",
        "company__name",
        "farm__name",
        "created_by__username",
        "approved_by__username",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(Pond)
class PondAdmin(admin.ModelAdmin):
    list_display = ('id', 'pond_name', 'pond_type', 'pond_use', 'farm', 'company', 'status', 'created_date')
    list_filter = ('pond_type', 'pond_use', 'status', 'farm', 'company')
    search_fields = ('pond_name',)
    readonly_fields = ('created_date',)
    ordering = ('-created_date',)


@admin.register(PondUseStats)
class PondUseStatsAdmin(admin.ModelAdmin):
    list_display = ('id', 'pond_name', 'batch', 'harvest_stage', 'start_weight', 'harvest_weight', 'harvest_date', 'start_date', 'status', 'created_by', 'approver_id', 'created_date')
    list_filter = ('harvest_stage', 'status', 'farm', 'company')
    search_fields = ('pond_name',)
    readonly_fields = ('pond_name', 'created_date')
