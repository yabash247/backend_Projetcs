from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import generics, status
from users.models import User, UserProfile
from .serializers import UserSerializer, CustomTokenObtainPairSerializer, UserProfileSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
import random
from rest_framework.parsers import JSONParser
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import devices_for_user

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        otp_code = random.randint(100000, 999999)
        user.otp_code = otp_code
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
        otp_code = request.data.get('otp')
        new_password = request.data.get('password')
        user = User.objects.filter(otp_code=otp_code).first()
        if user:
            user.set_password(new_password)
            user.otp_code = None
            user.save()
            return Response({'message': 'Password reset successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid OTP'}, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(generics.RetrieveUpdateAPIView):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.profile
     
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

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