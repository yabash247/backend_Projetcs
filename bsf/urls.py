# urls.py
from django.urls import path
from .views import FarmListCreateView, FarmDetailView, FarmPutViews, StaffMemberListCreateView, StaffMemberDetailView
from .views import NetListCreateView, NetDetailView, BatchListCreateView, BatchDetailView


urlpatterns = [

    # Farm URLs
    path('farms/create/', FarmListCreateView.as_view(), name='farm-list-create'),
    path('branch/', FarmDetailView.as_view(), name='farm-detail-view'),
    path('farms/edit/<int:pk>/', FarmPutViews.as_view(), name='farm-edit-and-delete'),

    # Staff Member URLs
    path('farms/staff-members/add/', StaffMemberListCreateView.as_view(), name='staff-member-list-create'),
    path('branch/staff-members/', StaffMemberDetailView.as_view(), name='staff-member-detail'),

    # Net URLs
    path('nets/', NetListCreateView.as_view(), name='net-list-create'),
    path('nets/<int:pk>/', NetDetailView.as_view(), name='net-detail'),

    # Batch URLs
    path('batches/', BatchListCreateView.as_view(), name='batch-list-create'),
    path('batches/<int:pk>/', BatchDetailView.as_view(), name='batch-detail'),
    
]


from .views import DurationSettingsListCreateView, DurationSettingsDetailView
urlpatterns += [
    path("duration-settings/", DurationSettingsListCreateView.as_view(), name="duration-settings-list-create"),
    path("duration-settings/", DurationSettingsDetailView.as_view(), name="duration-settings-detail"),
]

from .views import NetUseStatsListCreateView, NetUseStatsDetailView

urlpatterns += [
    path("net-use-stats/", NetUseStatsListCreateView.as_view(), name="net-use-stats-list-create"),
    path("net-use-stats/<int:pk>/", NetUseStatsDetailView.as_view(), name="net-use-stats-detail"),
]