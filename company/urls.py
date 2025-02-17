from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AddCompanyView, EditCompanyView, DeleteCompanyView, ViewCompanyView, AuthorityView, AddAuthorityView, EditAuthorityView, DeleteAuthorityView, ViewStaffView, AddStaffView, EditStaffView, DeleteStaffView
from .views import AddStaffLevelView, EditStaffLevelView, DeleteStaffLevelView, StaffLevelView, BranchListCreateView, BranchDetailView, MediaListCreateView, MediaDetailView, apiTest


router = DefaultRouter()
#router.register(r'authorities', AuthorityViewSet)

urlpatterns = [

    #path('api/', include(router.urls)),

    path('test/', apiTest.as_view(), name='api_Test'),
    path('add/', AddCompanyView.as_view(), name='add-company'),
    path('<int:pk>/edit/', EditCompanyView.as_view(), name='edit-company'),
    path('<int:pk>/delete/', DeleteCompanyView.as_view(), name='delete-company'),
    path('', ViewCompanyView.as_view(), name='list-companies'),  

    path('authorities/<int:company_id>/', AuthorityView.as_view(), name='authority_view'),
    path('authorities/add/', AddAuthorityView.as_view(), name='add-authority'),
    path('authorities/<int:pk>/edit/', EditAuthorityView.as_view(), name='edit-authority'),
    path('authorities/<int:pk>/delete/', DeleteAuthorityView.as_view(), name='delete-authority'),

    path('<int:company_id>/staff/', ViewStaffView.as_view(), name='view-staff'),
    path('<int:company_id>/staff/<int:staff_id>/', ViewStaffView.as_view(), name='view-specific-staff'),
    path('staff/add/', AddStaffView.as_view(), name='add-staff'),
    path('staff/<int:pk>/edit/', EditStaffView.as_view(), name='edit-staff'),
    path('staff/<int:pk>/delete/', DeleteStaffView.as_view(), name='delete-staff'),

    path('staff/stafflevels/<int:company_id>/<int:user_id>/', StaffLevelView.as_view(), name='staff_level_view'),
    path('stafflevels/add/', AddStaffLevelView.as_view(), name='add-stafflevel'),
    path('stafflevels/<int:pk>/edit/<int:id>/', EditStaffLevelView.as_view(), name='edit-stafflevel'),
    path('stafflevels/<int:pk>/delete/', DeleteStaffLevelView.as_view(), name='delete-stafflevel'),

    path('branches/', BranchListCreateView.as_view(), name='branch-list-create'),
    path('branches/<int:pk>/', BranchDetailView.as_view(), name='branch-detail'),

    path("media/", MediaListCreateView.as_view(), name="media-list-create"),
    path("media/<int:pk>/", MediaDetailView.as_view(), name="media-detail"),

]

from .views import TaskListCreateView, TaskDetailView, Recurance, CustomTaskView
urlpatterns += [
    path('tasks/', TaskListCreateView.as_view(), name='task-list-create'),
    path('tasks/<int:pk>/', TaskDetailView.as_view(), name='task-detail'),

    path('task/recurrence/', Recurance.as_view(), name='recurrence'),
    path('custom-task/', CustomTaskView.as_view(), name='custom-task'),
]


from .views import ActivityOwnerListCreateView, ActivityOwnerDetailView
urlpatterns += [
    path('activity-owners/', ActivityOwnerListCreateView.as_view(), name='activity-owner-list-create'),
    path('activity-owners/<int:pk>/', ActivityOwnerDetailView.as_view(), name='activity-owner-detail'),
]


# Path: backend/company/urls.py
from .views import RewardsPointsTrackerView
urlpatterns = [
    # Retrieve rewards for the logged-in user
    path('rewards/', RewardsPointsTrackerView.as_view(), name='rewards-list'),

    # Retrieve rewards for a specific user (if permitted)
    path('rewards/user/<int:user_id>/', RewardsPointsTrackerView.as_view(), name='rewards-by-user'),

    # Retrieve rewards for a specific company (most recent per branch)
    path('rewards/company/<int:company_id>/', RewardsPointsTrackerView.as_view(), name='rewards-by-company'),

    # Retrieve rewards for a specific branch (most recent)
    path('rewards/branch/<int:branch_id>/', RewardsPointsTrackerView.as_view(), name='rewards-by-branch'),

    # Retrieve rewards for the logged-in user for a specific company (all most recent per company branch)
    path('rewards/company/<int:company_id>/most_recent/', RewardsPointsTrackerView.as_view(), name='rewards-most-recent-company'),

    # Retrieve rewards for the logged-in user for a specific branch in a company
    path('rewards/company/<int:company_id>/branch/<int:branch_id>/', RewardsPointsTrackerView.as_view(), name='rewards-by-company-branch'),
]



from .views import UserMostRecentRewardsView

urlpatterns = [
    # Retrieve most recent rewards for the logged-in user per company branch
    path('rewards/my-recent/', UserMostRecentRewardsView.as_view(), name='my-most-recent-rewards'),
]
