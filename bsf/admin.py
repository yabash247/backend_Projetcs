from django.contrib import admin
from .models import StaffMember, Farm, Net, Batch, DurationSettings

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
