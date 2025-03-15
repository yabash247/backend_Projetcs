# urls.py
from django.urls import path
from .views import FarmListCreateView, FarmDetailView, FarmPutViews, StaffMemberListCreateView, StaffMemberDetailView
from .views import NetListCreateView, NetDetailView, NetDetailView_status, BatchListCreateView, BatchDetailView
from .views import NetUseStatsListCreateView, NetUseStatsDetailView, NetUseStatsRetrieveAllView


urlpatterns = [

    # Farm URLs
    path('farms/create/', FarmListCreateView.as_view(), name='farm-list-create'),
    path('branch/', FarmDetailView.as_view(), name='farm-detail-view'),
    path('farms/edit/<int:pk>/', FarmPutViews.as_view(), name='farm-edit-and-delete'),

    # Staff Member URLs
    path('branch/staff-members/add/', StaffMemberListCreateView.as_view(), name='staff-member-list-create'),
    path('staff-members/', StaffMemberDetailView.as_view(), name='staff-member-detail'),

    # Net URLs
    path('nets/', NetListCreateView.as_view(), name='net-list-create'),
    path('nets/<int:pk>/', NetDetailView.as_view(), name='net-detail'),
    path('nets_statsCheck/', NetDetailView_status.as_view(), name='net-detail-satsCheck'),

    # Batch URLs
    path('batches/', BatchListCreateView.as_view(), name='batch-list-create'),
    path('batches/<int:pk>/', BatchDetailView.as_view(), name='batch-detail'),

    # Net Use Status URLs
    path("net-use-stats/", NetUseStatsListCreateView.as_view(), name="net-use-stats-list-create"),
    path("net-use-stats/<int:pk>/", NetUseStatsDetailView.as_view(), name="net-use-stats-detail"),
    path("net-use-stats/retrieve-all/", NetUseStatsRetrieveAllView.as_view(), name="net-use-stats-retrieve-all"),
    
]


from .views import DurationSettingsListCreateView, DurationSettingsDetailView
urlpatterns += [
    path("duration-settings/", DurationSettingsListCreateView.as_view(), name="duration-settings-list-create"),
    path("duration-settings/", DurationSettingsDetailView.as_view(), name="duration-settings-detail"),
]



# Fetch all ponds, available ponds, or a specific pond by ID
from .views import PondView
urlpatterns += [
    path('ponds/', PondView.as_view(), name='pond-list-create'),  # View all or create
    path('ponds/', PondView.as_view(), name='pond-list'),
    path('ponds/<int:id>/', PondView.as_view(), name='pond-detail-edit'),  # View by ID or edit
    
]



from .views import PondUseStatsView, PondUseStats
urlpatterns += [
    path('ponduse-stats/', PondUseStatsView.as_view(), name='ponduse-stats-list-create'),
    path('ponduse-stats/<int:id>/', PondUseStatsView.as_view(), name='ponduse-stats-detail-edit'),
    path('pondsTask', PondUseStats.as_view(), name='pond-task'),  
]


from .views import WhatsAppTaskView
urlpatterns += [
    path('whatsapp/task/', WhatsAppTaskView.as_view(), name='whatsapp-task'),
]

from .views import WhatsAppTaskTest
urlpatterns += [
    path('whatsapp/test/', WhatsAppTaskTest.as_view(), name='whatsapp-test'),
]


