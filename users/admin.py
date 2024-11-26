from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'title', 'phone')
    search_fields = ('user__username', 'first_name', 'last_name')
    list_filter = ('title', 'user__is_active')
    ordering = ('user__username',)
    fieldsets = (
        (None, {
            'fields': ('user', 'first_name', 'last_name', 'title', 'phone')
        }),
        ('Permissions', {
            'fields': ('user__is_active', 'user__is_staff')
        }),
    )

# Register your models here.
