# urls.py
from django.urls import path
from .views import FarmListCreateView, FarmDetailView, FarmPutViews, StaffMemberListCreateView, StaffMemberDetailView


urlpatterns = [
    path('farms/create/', FarmListCreateView.as_view(), name='farm-list-create'),
    path('branch/', FarmDetailView.as_view(), name='farm-detail-view'),
    path('farms/edit/<int:pk>/', FarmPutViews.as_view(), name='farm-edit-and-delete'),

    # Staff Member URLs
    path('farms/staff-members/', StaffMemberListCreateView.as_view(), name='staff-member-list-create'),
    path('farms/staff-members/<int:pk>/', StaffMemberDetailView.as_view(), name='staff-member-detail'),

]
