from django.db import models
import os
from users.models import User 
from django.utils.timezone import now
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator



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
    creator = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='created_companies')  # Creator
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


class Branch(models.Model):
    """
    Tracks all farms/branches of a company.
    Auto-populates with details from the referenced farm in the `bsf` app.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=255)
    branch_id = models.IntegerField(unique=True)  # Stores the ID of the related farm in the `bsf` app
    status = models.CharField(max_length=20)  # Matches the status of the farm in the `bsf` app
    appName = models.CharField(max_length=255, default="bsf")  # Referenced app name
    modelName = models.CharField(max_length=255, default="Farm")  # Referenced model name
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.company.name} ({self.status})"  


class Staff(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='staff_records')  # Link to user model
    company = models.ForeignKey('Company', on_delete=models.CASCADE, related_name='staff')  # Link to company model
    work_phone = models.CharField(
        max_length=20,
        #unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(regex=r'^\+?1?\d{9,15}$', message="Phone number must be valid and between 9-15 digits.")]
    )  # Optional work phone
    work_email = models.EmailField(
        max_length=254,
        blank=True,
        null=True,
        #unique=Trueself.work_phone
    )  # Optional work email
    date_created = models.DateTimeField(default=now)  # Auto timestamp for creation
    joined_company_date = models.DateTimeField(
        null=True, blank=True
    )  # Requires higher permissions to edit
    comments = models.TextField(max_length=2000, blank=True, null=True)  # Optional comments
    added_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='added_staff'
    )  # User who added this record
    approved_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_staff'
    )  # User who approved this record

    def __str__(self):
        return f"Staff: {self.user} at {self.company}"

    class Meta:
        verbose_name = "Staff"
        verbose_name_plural = "Staff"
        unique_together = ('user', 'company')  # Prevent duplicate user-company records

    def clean(self):
        """
        Custom validation logic to prevent conflicts.
        """
        # Ensure work_email and work_phone are unique across staff records
        if self.work_email:
            if Staff.objects.filter(work_email=self.work_email, company=self.company).exclude(id=self.id).exists():
                raise ValidationError(f"This work email:{self.work_email} is already assigned to another staff.")
        if self.work_phone:
            if Staff.objects.filter(work_phone=self.work_phone, company=self.company).exclude(id=self.id).exists():
                raise ValidationError(f"This work phone:{self.work_phone} is already assigned to another staff.")

    def save(self, *args, **kwargs):
        self.full_clean()  # Run validations
        super().save(*args, **kwargs)


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


def media_upload_path(instance, filename):
    """
    Define the dynamic upload path for media files.
    Format: media/company/<branch>/<app_name>/<model_name>/<model_id>/<id>/<filename>
    """
    path = f"media/company/"
    if instance.app_name != "company":
        path += f"{instance.branch.id}/"
    path += f"{instance.app_name}/{instance.model_name}/{instance.model_id}/{instance.id or 'new'}/{filename}"
    return path


class Media(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="media")
    branch = models.ForeignKey(
        Branch, null=True, blank=True, on_delete=models.SET_NULL, related_name="media"
    )
    app_name = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    model_id = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True, null=True)
    file = models.FileField(upload_to=media_upload_path)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="inactive")
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="uploaded_media"
    )
    created_date = models.DateTimeField(default=now)
    negative_flags_count = models.PositiveIntegerField(default=0)
    comments = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Media {self.title} - {self.app_name}/{self.model_name}"

    def save(self, *args, **kwargs):
        """
        Custom save method to create directories if they don't exist.
        """
        # Call the parent save method to populate the ID if new
        super().save(*args, **kwargs)

        # Create directories if they don't exist
        upload_dir = os.path.dirname(self.file.path)
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

    def clean(self):
        """
        Custom validation logic.
        """
        # Ensure that branch is not provided if app_name == "company"
        if self.app_name == "company" and self.branch:
            raise ValidationError("Branch cannot be specified for the 'company' app.")

    class Meta:
        verbose_name = "Media"
        verbose_name_plural = "Media"
        ordering = ["-created_date"]


