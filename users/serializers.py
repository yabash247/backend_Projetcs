from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import UserProfile

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'email_verified']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['username'] = self.user.username
        return data

class UserProfileSerializer(serializers.ModelSerializer):
    associated_user_data = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'profile_image',
            'bio',
            'first_name',
            'last_name',
            'title',
            'website',
            'phone',
            'birthday',
            'age',
            'associated_user_data',  # New field
        ]

    def get_associated_user_data(self, obj):
        """
        Fetch and serialize the associated user data.
        """
        user = obj.user  # Access the related User object
        return UserSerializer(user).data

    def update(self, instance, validated_data):
        instance.profile_image = validated_data.get('profile_image', instance.profile_image)
        instance.bio = validated_data.get('bio', instance.bio)
        instance.save()
        return instance

