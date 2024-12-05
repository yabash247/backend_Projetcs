# models.py
from django.db import models
from django.contrib.auth import get_user_model
from company.models import Company
from django.core.exceptions import ValidationError
from difflib import SequenceMatcher
from django.utils.timezone import now

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


class Net(models.Model):  # New model for Black Soldier Fly's Love Cage
    """
    Represents a breathable artificial habitat for Black Soldier Fly (Love Cage).
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('dormant', 'Dormant'),
        ('broken', 'Broken'),
    ]

    name = models.CharField(max_length=255, help_text="Name of the Net (Love Cage).")
    length = models.FloatField(help_text="Length of the Net in meters.")
    width = models.FloatField(help_text="Width of the Net in meters.")
    height = models.FloatField(help_text="Height of the Net in meters.")
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='active', help_text="Status of the Net."
    )
    created_at = models.DateTimeField(default=now, help_text="Timestamp when the Net was created.")
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="nets", help_text="The company owning the Net."
    )
    farm = models.ForeignKey(
        Farm, on_delete=models.CASCADE, related_name="nets", help_text="The farm to which the Net is assigned."
    )

    def __str__(self):
        return f"{self.name} (Farm: {self.farm.name}, Company: {self.company.name})"

    class Meta:
        verbose_name = "Net"
        verbose_name_plural = "Nets"
        unique_together = ('name', 'farm', 'company')  # Ensure unique Net name within the same farm and company



class Batch(models.Model):
    EXPECTATION_CHOICES = [
        (5, "Outstanding"),
        (4, "Exceeds Fully Successful"),
        (3, "Fully Successful"),
        (2, "Minimally Satisfactory"),
        (1, "Unsatisfactory"),
    ]

    STATUS_CHOICES = [
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
    ]

    batch_name = models.CharField(max_length=10)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="batches")
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="batches")
    cretated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="created_batches", null=True)
    

    laying_start_date = models.DateField(null=True, blank=True)
    laying_end_date = models.DateField(null=True, blank=True)
    laying_harvest_quantity = models.PositiveIntegerField(null=True, blank=True)
    laying_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ongoing")
    laying_expectation_reached = models.IntegerField(choices=EXPECTATION_CHOICES, null=True, blank=True)

    incubation_start_date = models.DateField(null=True, blank=True)
    incubation_end_date = models.DateField(null=True, blank=True)
    incubation_start_quantity = models.PositiveIntegerField(null=True, blank=True)
    incubation_harvest_quantity = models.PositiveIntegerField(null=True, blank=True)
    incubation_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ongoing")
    incubation_expectation_reached = models.IntegerField(choices=EXPECTATION_CHOICES, null=True, blank=True)

    nursery_start_date = models.DateField(null=True, blank=True)
    nursery_end_date = models.DateField(null=True, blank=True)
    nursery_start_quantity = models.PositiveIntegerField(null=True, blank=True)
    nursery_harvest_quantity = models.PositiveIntegerField(null=True, blank=True)
    nursery_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ongoing")
    nursery_expectation_reached = models.IntegerField(choices=EXPECTATION_CHOICES, null=True, blank=True)

    growout_start_date = models.DateField(null=True, blank=True)
    growout_end_date = models.DateField(null=True, blank=True)
    growout_start_quantity = models.PositiveIntegerField(null=True, blank=True)
    growout_harvest_quantity = models.PositiveIntegerField(null=True, blank=True)
    growout_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ongoing")
    growout_expectation_reached = models.IntegerField(choices=EXPECTATION_CHOICES, null=True, blank=True)

    puppa_start_date = models.DateField(null=True, blank=True)
    puppa_end_date = models.DateField(null=True, blank=True)
    puppa_start_quantity = models.PositiveIntegerField(null=True, blank=True)
    puppa_harvest_quantity = models.PositiveIntegerField(null=True, blank=True)
    puppa_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ongoing")
    puppa_expectation_reached = models.IntegerField(choices=EXPECTATION_CHOICES, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("batch_name", "farm")  # Unique constraint for batch_name and farm

    def __str__(self):
        return f"{self.batch_name} - {self.farm.name}"

    def save(self, *args, **kwargs):
        if not self.batch_name:
            self.batch_name = self.generate_batch_name()
        super().save(*args, **kwargs)

    def generate_batch_name(self):
        """
        Generates a unique batch name based on the farm.
        Follows the pattern: AA1, AA2 ... AA10, AB1, AB2 ... AB10
        """
        last_batch = Batch.objects.filter(farm=self.farm).order_by("created_at").last()
        if not last_batch:
            return "AA1"

        # Extract prefix and number from the last batch name
        last_name = last_batch.batch_name
        prefix, number = last_name[:-1], int(last_name[-1])

        if number < 10:
            return f"{prefix}{number + 1}"
        else:
            # Increment prefix (e.g., AA -> AB)
            new_prefix = self.increment_prefix(prefix)
            return f"{new_prefix}1"

    @staticmethod
    def increment_prefix(prefix):
        """
        Increments the prefix alphabetically (e.g., AA -> AB, AZ -> BA)
        """
        prefix_list = list(prefix)
        for i in range(len(prefix_list) - 1, -1, -1):
            if prefix_list[i] != "Z":
                prefix_list[i] = chr(ord(prefix_list[i]) + 1)
                break
            prefix_list[i] = "A"
        return "".join(prefix_list)


class DurationSettings(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="duration_settings")
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, null=True, blank=True, related_name="duration_settings")
    
    laying_duration = models.PositiveIntegerField(default=0, help_text="Duration for laying in days")
    nursery_duration = models.PositiveIntegerField(default=0, help_text="Duration for nursery in days")
    incubation_duration = models.PositiveIntegerField(default=0, help_text="Duration for incubation in days")
    growout_duration = models.PositiveIntegerField(default=0, help_text="Duration for grow-out in days")
    puppa_in_net_replenishment_duration = models.PositiveIntegerField(default=0, help_text="Duration for puppa replenishment in days")

    feed1_fermentation_period = models.PositiveIntegerField(default=0, help_text="Duration for feed1 fermentation in days")
    feed2_fermentation_period = models.PositiveIntegerField(default=0, help_text="Duration for feed2 fermentation in days")
    attractant_duration = models.PositiveIntegerField(default=0, help_text="Duration for attractant in days")
    general_inspection_duration = models.PositiveIntegerField(default=0, help_text="Duration for general inspection in days")
    net_cleanup_duration = models.PositiveIntegerField(default=0, help_text="Duration for net cleanup in days")

    class Meta:
        unique_together = ("company", "farm")

    def __str__(self):
        return f"DurationSettings for {self.farm.name if self.farm else 'Default'} in {self.company.name}"


class NetUseStats(models.Model):
    STATUS_CHOICES = [
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="net_use_stats")
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="net_use_stats")
    net = models.ForeignKey(Net, on_delete=models.CASCADE, related_name="net_use_stats")
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="net_use_stats")

    lay_start = models.DateTimeField()
    lay_end = models.DateTimeField(null=True, blank=True)
    harvest_weight = models.FloatField(null=True, blank=True, help_text="Harvest weight in grams")

    stats = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ongoing")

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_net_use_stats")
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_net_use_stats")

    created_at = models.DateTimeField(default=now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"NetUseStats for {self.net.name} in Batch {self.batch.batch_name}"

