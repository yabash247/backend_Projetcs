from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework import generics, status
from users.models import User, UserProfile
from .serializers import UserSerializer, CustomTokenObtainPairSerializer, UserProfileSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
import random
from rest_framework.parsers import JSONParser
from django_otp.plugins.otp_totp.models import TOTPDevice
from company.task import check_and_generate_tasks
from django_otp import devices_for_user
from django.shortcuts import get_object_or_404

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        otp_code = random.randint(100000, 999999)
        user.otp_code = otp_code
        user.email = user.email.lower()
        user.save()
        send_mail(
            'Verify Your Email',
            f'Your OTP is: {otp_code}',
            'no-reply@example.com',
            [user.email],
        )

class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    

    def post(self, request):
        data = JSONParser().parse(request)
        otp_code = data["otp"]
        user = User.objects.filter(otp_code=otp_code).first()
        if user:
            user.email_verified = True
            user.otp_code = None
            user.save()
            return Response({'message': 'Email verified successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)
    
class PasswordRecoveryView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        email = email.lower()
        user = User.objects.filter(email=email).first()
        if user:
            otp_code = random.randint(100000, 999999)
            user.otp_code = otp_code
            user.save()
            send_mail(
                'Password Reset OTP',
                f'Your OTP is: {otp_code}',
                'no-reply@example.com',
                [email],
            )
            return Response({'message': 'OTP sent to your email'}, status=status.HTTP_200_OK)
        return Response({'error': 'Email not found'}, status=status.HTTP_404_NOT_FOUND)

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        email = email.lower()
        otp_code = request.data.get('otp')
        new_password = request.data.get('password')
        user = User.objects.filter(otp_code=otp_code, email=email).first()
        if user:
            user.set_password(new_password)
            user.otp_code = None
            user.save()
            return Response({'message': 'Password reset successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)

class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'id'


class UserProfileView(generics.RetrieveUpdateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """
        Override to return the authenticated user's profile.
        """
        return self.request.user.profile

     
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Endpoint to return the currently logged-in user's data
    """
    user = request.user
    if user.is_authenticated:
        return Response({
            'id': user.id,
            'name': user.first_name + ' ' + user.last_name if user.first_name and user.last_name else user.username,
            'email': user.email,
        })
    else:
        return Response({'error': 'User is not authenticated'}, status=401)


    '''
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        user = User.objects.get(username=request.data.get('username'))

        if user.get_totp_device() and user.get_totp_device().confirmed:
            response.data['requires_2fa'] = True
            # Do not issue tokens until 2FA is verified
            #serializer_class = CustomTokenObtainPairSerializer
            return response
        else:
            return response
    '''

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

class EnableTOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Generate a new TOTP device
        device, created = TOTPDevice.objects.get_or_create(user=request.user, name="default")
        if created:
            device.confirmed = False  # Device is not confirmed yet
            device.save()
        return Response({'qr_code_url': device.config_url}, status=200)

    def post(self, request):
        otp = request.data.get('otp')
        device = request.user.get_totp_device()
        if device and device.verify_token(otp):
            device.confirmed = True
            device.save()
            return Response({'message': 'TOTP enabled successfully'}, status=200)
        return Response({'error': 'Invalid OTP'}, status=400)

class VerifyTOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        otp = request.data.get('otp')
        device = request.user.get_totp_device()
        if device and device.verify_token(otp):
            return Response({'message': '2FA verification successful'}, status=200)
        return Response({'error': 'Invalid OTP'}, status=400)
    
from django.http import JsonResponse
class UserPhoneView(APIView):
    """
    API to retrieve a user's phone number from UserProfile.
    """
    def get(self, request, user_id):
        user_profile = get_object_or_404(UserProfile, user_id=user_id)
        return JsonResponse({"phone": user_profile.phone})



from .whatsAppHelper import WhatsAppLoginHandler, WhatsAppHelpHandler, WhatsAppTaskHandler, WhatsAppUtils
from django.core.cache import cache

class WhatsAppView(APIView):
    """
    Handles WhatsApp login, task retrieval, and execution.
    """

    def post(self, request, *args, **kwargs):
        sender = request.data.get("From")
        message = request.data.get("Body", "").strip()
        sender_phone = sender.replace("whatsapp:", "").strip()
        self.media_url = request.data.get("MediaUrl0")

        if message.lower().startswith("help"):
            help_handler = WhatsAppHelpHandler(sender_phone, message)
            return help_handler.process_help_request()

        # ✅ Step 0: Initialize Login 
        login_handler = WhatsAppLoginHandler(sender_phone, message)

        # ✅ Step 1: Check if login is ongoing
        # ✅ Step 1: Check if login is ongoing and pending confirmation
        if cache.get(f"whatsapp_login_state_{sender_phone}") and cache.get(f"whatsapp_pending_confirmation_{sender_phone}"):
            return login_handler.handle_login_confirmation()

        # ✅ Step 2: Check if the user is logged in or needs authentication
        user = login_handler.get_user() or login_handler.check_existing_login()

        # ✅ Define user_id from retrieved user
        user_id = user.id if user else None 

        # ✅ Step 3: If a login request is detected, process it
        if message.lower().startswith("login "):
            cache.set(f"whatsapp_login_state_{sender_phone}", True, timeout=600)  # ✅ Login process starts
            return login_handler.process_manual_login()

        # ✅ Step 4: If using another staff’s phone, ask for login confirmation
        if user and not login_handler.is_login_confirmed():
            cache.set(f"whatsapp_login_state_{sender_phone}", True, timeout=600)  # ✅ Login process starts
            return login_handler.welcome_and_confirm_login()

        # ✅ Step 5: If user confirms login, handle their response
        if message.strip() in ["1", "2"]:
            response = login_handler.handle_login_confirmation() 
            cache.delete(f"whatsapp_login_state_{sender_phone}")  # ✅ Login process ends
            return response
        
        # ✅ Step 8: If a task is active, do NOT validate input
        active_task = cache.get(f"whatsapp_task_active_{user_id}", None)
        if active_task:
            task_handler = WhatsAppTaskHandler(request)  # ✅ Initialize first to set `task_id`
            return task_handler.process_whatsapp_task_step()  # ✅ Process task actions
        
        # ✅ Step 9: If a login request is detected, process it
        if message.lower().startswith("start task"):
             task_handler = WhatsAppTaskHandler(request)  # ✅ Initialize first to set `task_id`
             #print(task_handler.user_id)
             return task_handler.process_whatsapp_task_step()  # ✅ Now call function
        
        
        # ✅ Validate Input - Return error if not part of recognized actions or active session
        help_handler = WhatsAppHelpHandler(sender_phone, message)
        invalid_input_response = help_handler.validate_input()
        print(invalid_input_response)

        if invalid_input_response:
            return invalid_input_response

        
        # ✅ Step Final: Only send invalid input message if no active session
        if not cache.get(f"whatsapp_task_active_{user_id}"):
            return WhatsAppUtils.send_message(sender_phone, "❌ Invalid input. Send 'Help' for available commands.")

        return Response({"message": "Task session active, awaiting input."}, status=200)

