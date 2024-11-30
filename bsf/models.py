# models.py
from django.db import models
from django.contrib.auth import get_user_model
from company.models import Company  # Import Company model
from django.core.exceptions import ValidationError
from difflib import SequenceMatcher

User = get_user_model()

class Farm(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('closed', 'Closed'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="farms")
    creatorId = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_farms")
    name = models.CharField(max_length=255, help_text="Name of the farm.")
    description = models.TextField(help_text="General description of the farm.")
    established_date = models.DateField(help_text="Date the farm was established.", null=True, blank=True)
    location = models.CharField(max_length=255, help_text="Location of the farm.")
    contact_number = models.CharField(max_length=20, help_text="Contact number for the farm.")
    email = models.EmailField(help_text="Email address for inquiries.")
    website = models.URLField(blank=True, null=True, help_text="Website URL of the farm.")
    profile_image = models.ImageField(upload_to='farm/profile_images/', blank=True, null=True)
    background_image = models.ImageField(upload_to='farm/background_images/', blank=True, null=True)
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='inactive', 
        help_text="Current operational status of the farm."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Ensure unique farm name within the same company and location
        if Farm.objects.filter(name=self.name, company=self.company, location=self.location).exists():
            raise ValidationError(f"A farm with the name '{self.name}' already exists in this company and location.")

        # Warn about closely matching names
        farms_in_company = Farm.objects.filter(company=self.company)
        for farm in farms_in_company:
            similarity = SequenceMatcher(None, self.name.lower(), farm.name.lower()).ratio()
            if similarity > 0.8:  # Threshold for similarity warning
                raise ValidationError(
                    f"The name '{self.name}' is very similar to an existing farm: '{farm.name}'."
                )

    def save(self, *args, **kwargs):
        self.full_clean()  # Trigger the clean method before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.company.name} ({self.status})"


class StaffMember(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    POSITION_CHOICES = [
        ('worker', 'Worker'),
        ('manager', 'Manager'),
        ('director', 'Director'),
        ('managing_director', 'Managing Director'),
    ]

    LEVEL_CHOICES = [
        (1, 'Level 1'),
        (2, 'Level 2'),
        (3, 'Level 3'),
        (4, 'Level 4'),
        (5, 'Level 5'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="staff_members")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="staff_members")
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="staff_members")
    position = models.CharField(max_length=20, choices=POSITION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    level = models.IntegerField(choices=LEVEL_CHOICES, default=1)  # New level field
    assigned_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="created_staff_assignments", null=True)

    #class Meta:
        #unique_together = ('user', 'farm', 'company', 'status')  # Ensure no duplicates for user, farm, company, and status

    def __str__(self):
        return f"{self.user.username} - {self.position} at {self.farm.name} ({self.status}, Level {self.level})"

    

