from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FarmViewSet, PondViewSet, BatchViewSet, BatchMovementViewSet, 
    StockingHistoryViewSet, DestockingHistoryViewSet, StaffMemberViewSet,
    PondMaintenanceLogViewSet
)

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'farms', FarmViewSet, basename='farm')
router.register(r'ponds', PondViewSet, basename='pond')
router.register(r'batches', BatchViewSet, basename='batch')
router.register(r'batch-movements', BatchMovementViewSet, basename='batch-movement')
router.register(r'stocking-history', StockingHistoryViewSet, basename='stocking-history')
router.register(r'destocking-history', DestockingHistoryViewSet, basename='destocking-history')
router.register(r'staff-members', StaffMemberViewSet, basename='staff-member')
router.register(r'pond-maintenance', PondMaintenanceLogViewSet, basename='pond-maintenance')

# Include the API URLs in the main urlpatterns
urlpatterns = [
    path('', include(router.urls)),
]
