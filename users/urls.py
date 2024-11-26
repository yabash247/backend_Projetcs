from django.urls import path
from .views import (
    RegisterView, VerifyEmailView, PasswordRecoveryView, ResetPasswordView, UserProfileView, 
    CustomTokenObtainPairView, UserListView, EnableTOTPView, VerifyTOTPView, get_current_user
)

from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    path('recover-password/', PasswordRecoveryView.as_view(), name='recover_password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('me/', get_current_user, name='get_current_user'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('', UserListView.as_view(), name='user_list'),  # For testing authenticated route

    path('totp/enable/', EnableTOTPView.as_view(), name='enable_totp'),
    path('totp/verify/', VerifyTOTPView.as_view(), name='verify_totp'),
]


