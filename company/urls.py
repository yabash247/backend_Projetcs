from django.urls import path
from .views import AddCompanyView, EditCompanyView, DeleteCompanyView, ViewCompanyView, AddAuthorityView, EditAuthorityView, DeleteAuthorityView, ViewStaffView, AddStaffView, EditStaffView, DeleteStaffView
from .views import AddStaffLevelView, EditStaffLevelView, DeleteStaffLevelView

urlpatterns = [
    path('add/', AddCompanyView.as_view(), name='add-company'),
    path('<int:pk>/edit/', EditCompanyView.as_view(), name='edit-company'),
    path('<int:pk>/delete/', DeleteCompanyView.as_view(), name='delete-company'),
    path('<int:pk>/', ViewCompanyView.as_view(), name='view-company'),  # View a single company
    path('', ViewCompanyView.as_view(), name='list-companies'),  

    path('authorities/add/', AddAuthorityView.as_view(), name='add-authority'),
    path('authorities/<int:pk>/edit/', EditAuthorityView.as_view(), name='edit-authority'),
    path('authorities/<int:pk>/delete/', DeleteAuthorityView.as_view(), name='delete-authority'),

    path('<int:company_id>/staff/', ViewStaffView.as_view(), name='view-staff'),
    path('<int:company_id>/staff/<int:staff_id>/', ViewStaffView.as_view(), name='view-specific-staff'),
    path('staff/add/', AddStaffView.as_view(), name='add-staff'),
    path('staff/<int:pk>/edit/', EditStaffView.as_view(), name='edit-staff'),
    path('staff/<int:pk>/delete/', DeleteStaffView.as_view(), name='delete-staff'),

    path('stafflevels/add/', AddStaffLevelView.as_view(), name='add-stafflevel'),
    path('stafflevels/<int:pk>/edit/', EditStaffLevelView.as_view(), name='edit-stafflevel'),
    path('stafflevels/<int:pk>/delete/', DeleteStaffLevelView.as_view(), name='delete-stafflevel'),



]
