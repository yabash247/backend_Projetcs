from django.contrib import admin
from .models import UserProfile, User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'title', 'phone')
    search_fields = ('user', 'first_name', 'last_name')
    list_filter = ('title', 'user__is_active')
    ordering = ('user',)

# Register your models here.
