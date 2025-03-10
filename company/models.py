from django.db import models

import exifread  
import datetime
import requests
import os

from users.models import User 
from django.utils.timezone import now
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from geopy.geocoders import Nominatim

from pymediainfo import MediaInfo
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata



class Authority(models.Model):
    LEVELS = [
        ('1', 'One'),
        ('2', 'Two'),
        ('3', 'Three'),
        ('4', 'Four'),
        ('5', 'Five'),
    ]

    model_name = models.CharField(max_length=100, help_text="Name of the target model.")
    app_name = models.CharField(max_length=100, help_text="Name of the app the model belongs to.")  
    company = models.ForeignKey(
        'Company', on_delete=models.CASCADE, null=True, blank=True, related_name='authorities'
    )
    requested_by = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='authority_requests'
    )
    approver = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='authority_approvals'
    )

    view = models.CharField(max_length=1, choices=LEVELS, default='5')
    add = models.CharField(max_length=1, choices=LEVELS, default='5')
    edit = models.CharField(max_length=1, choices=LEVELS, default='5')
    delete = models.CharField(max_length=1, choices=LEVELS, default='5')
    accept = models.CharField(max_length=1, choices=LEVELS, default='5')
    approve = models.CharField(max_length=1, choices=LEVELS, default='5')

    created = models.DateTimeField(default=now)

    class Meta:
        verbose_name = "Authority"
        verbose_name_plural = "Authorities"
        unique_together = ('model_name', 'app_name', 'company')  # Ensure uniqueness for model and app per company

    def __str__(self):
        return f"Authority for {self.app_name}.{self.model_name} in {self.company}"

    def clean(self):
        """
        Custom validation logic to ensure data consistency.
        """
        if not self.model_name:
            raise ValidationError("Model name cannot be empty.")
        if not self.app_name:
            raise ValidationError("App name cannot be empty.")
        if not any([self.view, self.add, self.edit, self.delete, self.accept, self.approve]):
            raise ValidationError("At least one permission level must be defined.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def has_permission(self, user, action):
        """
        Check if a user has sufficient permission for a given action.
        """
        staff_level = StaffLevels.objects.filter(user=user, company=self.company).first()
        if not staff_level:
            return False
        required_level = int(getattr(self, action, '5'))
        return int(staff_level.level) >= required_level


class Company(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=100, unique=True)  # Unique company name
    description = models.TextField(blank=True, null=True)  # Optional description
    creator = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True, related_name='created_companies')  # Creator
    approver = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_companies')  # Approver
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be between 9 and 15 digits and start with + or a digit.")]  # Regex for phone numbers
    )
    email = models.EmailField(max_length=254, unique=True)  # Unique email
    website = models.URLField(max_length=200, blank=True, null=True)  # Optional validated URL
    comments = models.TextField(blank=True, null=True)  # Admin comments
    created_date = models.DateTimeField(default=now)  # Auto timestamp
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='inactive')  # Status with choices

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        ordering = ['-created_date']

    def clean(self):
        """
        Add custom validations.
        """
        # Example: Ensure website uses HTTPS if provided
        if self.website and not self.website.startswith("https://"):
            raise ValidationError("The website URL must start with https://")
        # Example: Restrict certain names
        if self.name.lower() in ['test', 'dummy']:
            raise ValidationError("Company name cannot be 'test' or 'dummy'.")
    
    def has_permission(self, user, action):
        """
        Check if a user has sufficient permission for a given action.
        :param user: User instance
        :param action: Permission type (view, add, edit, delete, accept, approve)
        :return: Boolean
        """
        # Get user's staff level for this company
        staff_level = StaffLevels.objects.filter(
            user=user,
            company=self.company
        ).first()

        if not staff_level:
            return False  # No staff level assigned to the user for this company

        # Get required permission level for the action
        required_level = int(getattr(self, action, '5'))  # Default to the highest level if undefined

        # Compare staff level with the required level
        return int(staff_level.level) >= required_level

    def save(self, *args, **kwargs):
        # Enforce default status to remain `inactive` unless changed by a super admin
        if self.pk:  # Editing an existing record
            original = Company.objects.get(pk=self.pk)
            if original.status != self.status and not self.creator.is_superuser:
                raise ValidationError("Only super admins can change the company status.")
        super().save(*args, **kwargs)

# 
class Branch(models.Model):
    """
    Tracks all farms/branches of a company.
    Auto-populates with details from the referenced farm in the `bsf` app.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=255)
    branch_id = models.IntegerField(unique=True)  # Stores the ID of the related farm in the `bsf` app
    status = models.CharField(max_length=20)  # Matches the status of the farm in the `bsf` app
    appName = models.CharField(max_length=255, default="company")  # Referenced app name
    modelName = models.CharField(max_length=255, default="branch")  # Referenced model name
    description = models.TextField(help_text="General description of the branch.", null=True, blank=True)
    established_date = models.DateField(help_text="Date the Sector was established.", null=True, blank=True)
    location = models.CharField(blank=True, null=True, max_length=255, help_text="Location of the Sector.")
    country = models.CharField(max_length=255, null=True, blank=True, help_text="Country where the branch is located.")
    contact_number = models.CharField(blank=True, null=True, max_length=20, help_text="Contact number for the Sector.")
    email = models.EmailField(help_text="Email address for inquiries.", null=True, blank=True)
    website = models.URLField(blank=True, null=True, help_text="Website URL of the Sector.") 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.company.name} ({self.status})"  




class Staff(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='staff_records')
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='staff')
    work_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be valid and between 9-15 digits.")]
    )
    salary = models.DecimalField(max_digits=15, decimal_places=3, null=True, blank=True, help_text="Monthly salary of the staff")
    reward_factor = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="Reward factor as a percentage of the salary"
    )
    reward = models.BooleanField(default=False, help_text="Determines if the user is eligible for reward points upon task completion.")
    work_email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
    )
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('fired', 'Fired'),
        ('retired', 'Retired'),
        ('resigned', 'Resigned'),
        ('pending', 'Pending'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    date_created = models.DateTimeField(default=now)
    joined_company_date = models.DateTimeField(
        null=True, blank=True
    )
    comments = models.TextField(max_length=2000, blank=True, null=True)
    added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='added_staff'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_staff'
    )

    def __str__(self):
        return f"Staff: {self.user.get_full_name() or self.user.email} at {self.company}"


    class Meta:
        verbose_name = "Staff"
        verbose_name_plural = "Staff"
        unique_together = ('user', 'company')

    def clean(self):
        if self.work_email:
            if Staff.objects.filter(work_email=self.work_email, company=self.company).exclude(id=self.id).exists():
                raise ValidationError(f"This work email: {self.work_email} is already assigned to another staff.")
        if self.work_phone:
            if Staff.objects.filter(work_phone=self.work_phone, company=self.company).exclude(id=self.id).exists():
                raise ValidationError(f"This work phone: {self.work_phone} is already assigned to another staff.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_max_reward_points_and_value(self):
        """
        Calculate the maximum reward points that can be allocated to a staff member per month
        and show the branch's country currency symbol.
        """
        if not (self.salary and self.reward_factor):
            return {
                "max_points": 0,
                "value_in_currency": 0,
                "currency_symbol": "N/A",
            }

        # Set fixed conversion rate
        conversion_rate = 643

        # Calculate max points
        max_points = self.salary * self.reward_factor * conversion_rate

        # Calculate value in currency
        value_in_currency = max_points / conversion_rate

        # Get branch and country details
        branch = self.company.branches.filter(staff_members__user=self.user).first()
        if not branch:
            return {
                "max_points": max_points,
                "value_in_currency": value_in_currency,
                "currency_symbol": "N/A",
            }

        country = branch.country

        # Fetch currency symbol from an online API
        try:
            response = requests.get(f"https://restcountries.com/v3.1/name/{country}?fullText=true")
            response.raise_for_status()
            country_data = response.json()[0]
            currency_symbol = list(country_data['currencies'].values())[0].get('symbol', "N/A")
        except Exception as e:
            currency_symbol = "N/A"  # Default to N/A if API fails

        return {
            "max_points": max_points,
            "value_in_currency": value_in_currency,
            "currency_symbol": currency_symbol,
        }

class StaffLevels(models.Model):
    LEVEL_CHOICES = [
        (1, 'Level 1'),
        (2, 'Level 2'),
        (3, 'Level 3'),
        (4, 'Level 4'),
        (5, 'Level 5'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, related_name='staff_levels')
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='staff_levels')
    level = models.PositiveSmallIntegerField(choices=LEVEL_CHOICES)
    created_date = models.DateTimeField(default=now)
    approver = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_levels')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.user} - {self.company} - Level {self.level}"

# Signal to enforce unique active status for userId and companyId
@receiver(pre_save, sender=StaffLevels)
def ensure_unique_active_status(sender, instance, **kwargs):
    if instance.status == 'active':
        StaffLevels.objects.filter(
            company=instance.company, 
            user=instance.user,
            status='active'
        ).exclude(pk=instance.pk).update(status='inactive')


# For reading metadata from media files


def media_upload_path(instance, filename):
    """
    Define the dynamic upload path for media files.
    Format: media/company/<branch>/<app_name>/<model_name>/<model_id>/<id>/<filename>
    """
    path = f"{instance.app_name}/{instance.model_name}/{instance.model_id}/{filename}"
    return path


class Media(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    company = models.ForeignKey(
        'Company', on_delete=models.CASCADE, related_name="media"
    )
    branch = models.ForeignKey(
        'Branch', null=True, blank=True, on_delete=models.SET_NULL, related_name="media"
    )
    app_name = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    model_id = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, null=True)
    file = models.FileField(upload_to=media_upload_path, max_length=1000)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="inactive"
    )
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="uploaded_media"
    )
    created_date = models.DateTimeField(default=now)
    creation_date = models.DateTimeField(null=True, blank=True, help_text="Date the video was created")
    creation_location = models.CharField(
        max_length=255, null=True, blank=True, help_text="Latitude and Longitude of the video"
    )
    negative_flags_count = models.PositiveIntegerField(default=0)
    comments = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Media {self.title} - {self.app_name}/{self.model_name}"

    def clean(self):
        """
        Custom validation logic.
        """
        if self.app_name == "company" and self.branch:
            raise ValidationError("Branch cannot be specified for the 'company' app.")

   
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    from pymediainfo import MediaInfo
    import exifread
    from datetime import datetime


    def extract_metadata(self):
        """
        Extract metadata such as creation date and location from the media file.
        This function dynamically determines the file type and uses the appropriate tool
        (hachoir, pymediainfo, or exifread) for metadata extraction.
        """
        if not self.file:
            return

        try:
            #file_path = self.file.path
            file_path = getattr(self.file, 'path', None)
            if not file_path or not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return
            print(f"Extracting metadata for: {file_path}")
            file_extension = file_path.split('.')[-1].lower()

            # Handle video files with pymediainfo or hachoir
            if file_extension in ['mp4', 'avi', 'mov', 'mkv']:
                self._extract_video_metadata(file_path)

            # Handle image files with exifread
            elif file_extension in ['jpg', 'jpeg', 'png', 'tiff']:
                self._extract_image_metadata(file_path)

            elif file_extension not in ['mp4', 'avi', 'mov', 'mkv', 'jpg', 'jpeg', 'png', 'tiff']:
                print(f"Unsupported file type: {file_extension}. Skipping metadata extraction.")
                return

            # Fallback for unsupported files (e.g., documents)
            else:
                print(f"File format not specifically supported: {file_extension}")

        except Exception as e:
            print(f"Error extracting metadata: {e}")


    def _extract_video_metadata(self, file_path):
        """
        Extract metadata from video files using pymediainfo and hachoir.
        """
        try:
            # Attempt to extract metadata using pymediainfo
            media_info = MediaInfo.parse(file_path)
            print(f"MediaInfo tracks: {media_info.tracks}")
            for track in media_info.tracks:
                if track.track_type == "General":
                    # Extract creation date
                    self.creation_date = track.recorded_date or track.tagged_date
                    print(f"Extracted creation date (pymediainfo): {self.creation_date}")

                    # Extract GPS location (if available, rare for videos)
                    if hasattr(track, 'location'):
                        self.creation_location = track.location
                        print(f"Extracted GPS location (pymediainfo): {self.creation_location}")

            # Fallback to hachoir if pymediainfo does not provide metadata
            if not self.creation_date:
                parser = createParser(file_path)
                if parser:
                    metadata = extractMetadata(parser)
                    if metadata:
                        self.creation_date = metadata.get('creation_date', None)
                        print(f"Extracted creation date (hachoir): {self.creation_date}")
                        self.creation_location = metadata.get('location', None)
                        print(f"Extracted GPS location (hachoir): {self.creation_location}")

        except Exception as e:
            print(f"Error extracting video metadata: {e}")


    def _extract_image_metadata(self, file_path):
        """
        Extract metadata from image files using exifread.
        """
        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f)

                # Extract creation date
                creation_date_tag = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
                if creation_date_tag:
                    try:
                        # Convert EXIF date format to datetime object
                        self.creation_date = datetime.strptime(creation_date_tag.values, "%Y:%m:%d %H:%M:%S")
                        print(f"Extracted creation date (exifread): {self.creation_date}")
                    except ValueError as ve:
                        print(f"Error parsing creation date: {ve}")

                else:
                    print("Creation date not found in EXIF tags.")

                # Extract GPS location
                gps_latitude = tags.get('GPS GPSLatitude')
                gps_latitude_ref = tags.get('GPS GPSLatitudeRef')
                gps_longitude = tags.get('GPS GPSLongitude')
                gps_longitude_ref = tags.get('GPS GPSLongitudeRef')
                if gps_latitude and gps_longitude and gps_latitude_ref and gps_longitude_ref:
                    self.creation_location = self._convert_gps_to_decimal(
                        gps_latitude, gps_latitude_ref, gps_longitude, gps_longitude_ref
                    )
                    print(f"Extracted GPS location (exifread): {self.creation_location}")

        except Exception as e:
            print(f"Error extracting image metadata: {e}")


    def _convert_gps_to_decimal(self, gps_latitude, gps_latitude_ref, gps_longitude, gps_longitude_ref):

        if not (gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref):
            print("Missing GPS tags. Cannot extract location.")
            return None
        """
        Converts GPS coordinates from EXIF format to decimal degrees.
        """
        def _convert_to_decimal(coord, ref):
            degrees = float(coord.values[0].num) / float(coord.values[0].den)
            minutes = float(coord.values[1].num) / float(coord.values[1].den) / 60
            seconds = float(coord.values[2].num) / float(coord.values[2].den) / 3600
            decimal = degrees + minutes + seconds
            if ref in ['S', 'W']:
                decimal = -decimal
            return decimal

        latitude = _convert_to_decimal(gps_latitude, gps_latitude_ref.values)
        longitude = _convert_to_decimal(gps_longitude, gps_longitude_ref.values)
        return f"{latitude}, {longitude}"
    
    def save(self, *args, **kwargs):
        try:
            print("Extracting metadata before saving...")
            self.extract_metadata()
            print(f"Metadata extracted: creation_date={self.creation_date}, creation_location={self.creation_location}")
        except Exception as e:
            print(f"Error during metadata extraction: {e}")
        super().save(*args, **kwargs)

    class Meta:
            verbose_name = "Media"
            verbose_name_plural = "Media"
            ordering = ["-created_date"]

       

class Task(models.Model): 
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('appeal', 'Appeal'), #task owner can appeal if a task can't be completed as required due to condictions beyond their control.
        ('pending', 'Pending'), # For tasks awaiting approval   
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rewardGranted', 'Reward Granted'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tasks")
    branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    farm = models.CharField(max_length=50, null=True, blank=True,)
    appName = models.CharField(max_length=50)
    modelName = models.CharField(max_length=50, blank=True, null=True)
    dataQuantity = models.PositiveIntegerField(
        default=1,
        help_text="Number of times modelName has to be filled out per task completion."
    )
    activity = models.CharField(max_length=50, blank=True, null=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    due_date = models.DateTimeField()
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="assigned_tasks")
    assistant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assistant")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    completed_date = models.DateTimeField(null=True, blank=True)
    completeDetails = models.TextField(blank=True, null=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="completed_by")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_tasks")
    approved_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    appealReason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.company.name})"

    class Meta:
        ordering = ['-created_at']

class ActivityDefaultSetting(models.Model):
    """
    Default settings for activities to be performed in a company's branch.
    This model can be used to store and manage default settings for various activities within an application, 
    ensuring that there are predefined minimum counts and durations for these activities.

    """
    name = models.CharField(max_length=255)
    appName = models.CharField(max_length=50)
    modelName = models.CharField(max_length=50)
    min_count = models.PositiveIntegerField(help_text="Estimated Minimum count/amount/times the activity needs to be performed monthly.")
    min_duration = models.DurationField(help_text="Estimated Minimum duration for the activity per count.", default=datetime.timedelta(hours=24))
    description = models.TextField(help_text="Description of the activity default setting.", null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.appName})"

    class Meta:
        verbose_name = "Activity Default Setting"
        verbose_name_plural = "Activity Default Settings"
        

class ActivityOwner(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

   
    company = models.ForeignKey(Company, on_delete=models.CASCADE,  null=True, blank=True, related_name='company')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='branch', default=None)
    default = models.ForeignKey('ActivityDefaultSetting', on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_owners')
    activity = models.CharField(max_length=255,  blank=True, null=True)
    dataQuantity = models.PositiveIntegerField(
        default=1,
        help_text="Number of times modelName has to be filled out per task completion."
    )
    mustFill = models.CharField(
        max_length=255,
        help_text="This is a test field that indicates what dataset must be filled out in the model (modelName) for the activity to be considered completed.",
        blank=True,
        null=True
    )
    importance_scale = models.PositiveIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text="Importance scale from 1 to 5 indicating how crucial the activity execution is to the success of the company's branch.",
        default=2
    )
    min_estimated_count = models.PositiveIntegerField(help_text="Minimum estimated amount (times, count) the activity needs to be performed every month.",  blank=True, null=True)
    reoccurring = models.BooleanField(default=False, help_text="Indicates if the activity is reoccurring.")
    interval_days = models.PositiveIntegerField(blank=True, null=True)  # Defines the interval for recurrence
    reoccurring_Start = models.DateField(blank=True, null=True, help_text="latest reoccuring start date. Only requireed if reoccuring is checked") # latest reoccuring start date
    reoccurring_End = models.DateField(blank=True, null=True, help_text="latest reoccuring end date. Only requireed if reoccuring is checked") # latest reoccuring end date
    appName = models.CharField(max_length=50, blank=True, null=True)
    modelName = models.CharField(max_length=50, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_activities')
    assistant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assisted_activities')
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='manager_activities')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_activities')
    created_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return f"{self.company} - {self.activity} ({self.status})"
    
    def save(self, *args, **kwargs):
        """
        Override save method to ensure min_estimated_count is set correctly.
        """
        default_setting = ActivityDefaultSetting.objects.filter(
                name=self.activity,
                appName=self.appName,
                modelName=self.modelName
            ).first()
        if default_setting:
            self.activity = default_setting.name
        if not self.min_estimated_count or self.min_estimated_count == 0:
            if default_setting:
                self.min_estimated_count = default_setting.min_count

        super().save(*args, **kwargs)
    

class RewardsPointsTracker(models.Model):
    """
    RewardsPointsTracker is a Django model that tracks the rewards points for users within a company.
    """
    TRANSACTION_TYPE_CHOICES = [
        ('merit', 'Merit'),
        ('assisted', 'Assisted'),
        ('pending', 'Pending'),
        ('staffMember', 'Staff Member'),
    ]

    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rewards_points')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='rewards_points')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='rewards_points')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='rewards_points')
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        default='merit',
        help_text="Type of transaction (merit, assisted, staffMember, pending)"
    )
    credit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,  help_text="Points received for the task")
    blocked = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,  help_text="Points blocked due to non task completion at all or in a timely manner")
    credit_date = models.DateTimeField(default=now, null=True, blank=True,  help_text="Date the points were received")
    point_conversion_rate = models.DecimalField(max_digits=10, null=True, blank=True,  decimal_places=2, help_text="Conversion rate of points to currency")
    debit = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True,  help_text="Points used by the user")
    debit_date = models.DateTimeField(null=True, blank=True, help_text="Date the points were used")
    debit_requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='points_requests')
    debit_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_points')
    comments = models.TextField(blank=True, null=True, help_text="Comments regarding the points transaction")
    points_available = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Points available for use")
    points_pending = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Points pending approval")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rewards Points Tracker for {self.user} - {self.company}"

    class Meta:
        verbose_name = "Rewards Points Tracker"
        verbose_name_plural = "Rewards Points Trackers"
        ordering = ['-credit_date']

    def save(self, *args, **kwargs):
        # Ensure points_available and points_pending are initialized
         # Fetch the last added record before the current one
        last_record = RewardsPointsTracker.objects.filter(
            user=self.user,
            company=self.company,
        ).exclude(pk=self.pk).order_by('-credit_date').first()

        if last_record :
            if self.transaction_type == 'pending':
                self.points_pending = last_record.points_pending + (self.credit or 0)
                self.points_available = last_record.points_available
            else:
                self.points_pending = last_record.points_pending
                self.points_available = last_record.points_available + (self.credit or 0)
        else:
            if self.transaction_type == 'pending':
                self.points_pending = self.credit or 0
                self.points_available = 0
            else:
                self.points_available = self.credit or 0
                self.points_pending = 0

        super().save(*args, **kwargs)


class Expectations(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    UOM_CHOICES = [
        ('kg', 'Kilograms'),
        ('g', 'Grams'),
        ('pcs', 'Pieces'),
        ('percentage', 'Percentage'),
        ('l', 'Liters'),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="expectations", help_text="The company associated with the expectation."
    )
    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="expectations", help_text="The branch associated with the expectation."
    )
    app_name = models.CharField(max_length=100, help_text="Name of the app.")
    model_name = models.CharField(max_length=100, help_text="Name of the model.")
    model_rowName = models.CharField(max_length=100, help_text="Name of the Col in the model.")
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='active', help_text="Status of the expectation."
    )
    quantity = models.FloatField(help_text="Quantity associated with the expectation.")
    uom = models.CharField(
        max_length=10, choices=UOM_CHOICES, default='pcs', help_text="Unit of Measurement (UOM)."
    )

    # Performance Levels
    poor = models.FloatField(help_text="Value for poor performance.")
    unsatisfactory = models.FloatField(help_text="Value for unsatisfactory performance.")
    satisfactory = models.FloatField(help_text="Value for satisfactory performance.")
    exceeds_expectation = models.FloatField(help_text="Value for exceeding expectations.")
    outstanding = models.FloatField(help_text="Value for outstanding performance.")

    created_date = models.DateTimeField(auto_now_add=True, help_text="The date when the expectation was created.")
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_expectations", help_text="User who created the expectation."
    )

    class Meta:
        verbose_name = "Expectation"
        verbose_name_plural = "Expectations"
        unique_together = ('company', 'branch', 'app_name', 'model_name', 'model_rowName')

    def __str__(self):
        return f"Expectation for {self.app_name}.{self.model_name} (Model ID: {self.model_rowName})"

    def clean(self):
        """
        Custom validation logic to ensure data consistency.
        """
        if not (self.poor < self.unsatisfactory < self.satisfactory < self.exceeds_expectation < self.outstanding):
            raise ValidationError(
                "Performance levels must be ordered: poor < unsatisfactory < satisfactory < exceeds expectation < outstanding."
            )

