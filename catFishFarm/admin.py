from django.contrib import admin
from .models import Farm, Pond, Batch, BatchMovement, StockingHistory, DestockingHistory, StaffMember

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'location', 'created_by', 'created_at')
    search_fields = ('name', 'company__name', 'location')
    list_filter = ('company', 'created_at')



@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    """
    Admin panel configuration for StaffMember model.
    """
    list_display = ("user", "company", "farm", "position", "status", "level", "assigned_at")
    list_filter = ("company", "farm", "status", "level")
    search_fields = ("user__username", "user__email", "company__name", "farm__name", "position")
    ordering = ("company", "farm", "level")
    readonly_fields = ("assigned_at", "created_by")
    
    fieldsets = (
        ("User Details", {
            "fields": ("user", "company", "farm", "leader")
        }),
        ("Staff Information", {
            "fields": ("position", "status", "level")
        }),
        ("System Details", {
            "fields": ("assigned_at", "created_by")
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Auto-assign the current admin user as `created_by` when adding a new staff member.
        """
        if not obj.created_by:
            obj.created_by = request.user
        obj.save()


@admin.register(Pond)
class PondAdmin(admin.ModelAdmin):
    list_display = ('name', 'farm', 'type', 'size', 'depth', 'created_at')
    search_fields = ('name', 'farm__name')
    list_filter = ('farm', 'type')

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'species', 'source', 'stocking_date', 'initial_quantity', 'initial_avg_weight', 'status')
    search_fields = ('name', 'species', 'source')
    list_filter = ('species', 'status', 'stocking_date')

@admin.register(BatchMovement)
class BatchMovementAdmin(admin.ModelAdmin):
    list_display = ('batch', 'from_pond', 'to_pond', 'moved_on')
    search_fields = ('batch__name', 'from_pond__name', 'to_pond__name')
    list_filter = ('moved_on',)

@admin.register(StockingHistory)
class StockingHistoryAdmin(admin.ModelAdmin):
    list_display = ('batch', 'stocked_at', 'pond', 'quantity', 'weight')
    search_fields = ('batch__name', 'pond__name')
    list_filter = ('stocked_at',)

@admin.register(DestockingHistory)
class DestockingHistoryAdmin(admin.ModelAdmin):
    list_display = ('batch', 'destocked_at', 'pond', 'quantity', 'weight', 'reason')
    search_fields = ('batch__name', 'pond__name')
    list_filter = ('destocked_at', 'reason')


