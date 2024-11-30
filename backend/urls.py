from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),  # Include user routes
    path('api/company/', include('company.urls')),
    path('accounts/', include('allauth.urls')),
    path('api/bsf/', include('bsf.urls')),
    #path('account/', include('two_factor.urls', 'two_factor')),  # 2FA routes
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
