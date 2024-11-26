from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),  # Include user routes
    path('api/company/', include('company.urls')),
    path('accounts/', include('allauth.urls')),
    #path('account/', include('two_factor.urls', 'two_factor')),  # 2FA routes
]
