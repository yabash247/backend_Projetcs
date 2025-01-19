from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import date
import os

from django_otp.plugins.otp_totp.models import TOTPDevice

def profile_image_path(instance, filename):
    base, ext = os.path.splitext(filename)
    return f"user/{instance.id}/{instance.id}{ext}"


class User(AbstractUser):
    # Add any custom fields if needed
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True, null=True)

    def get_totp_device(self):
        return TOTPDevice.objects.filter(user=self, confirmed=True).first()
    
    def profile(self):
        profile = UserProfile.objects.get(user=self)
   
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_image = models.ImageField(upload_to=profile_image_path, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

    @property
    def age(self):
        """Calculate age from birthday if available."""
        if self.birthday:
            today = date.today()
            return today.year - self.birthday.year - ((today.month, today.day) < (self.birthday.month, self.birthday.day))
        return None


# Signal to create or update a UserProfile instance whenever a User instance is created or updated
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        instance.profile.save()