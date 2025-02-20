from django.db import models
from django.contrib.auth import get_user_model
from company.models import Branch, Company, Media as CompanyMedia, Task as CompanyTask

User = get_user_model()

FEED_SIZE_CHOICES = [
    ('0.1mm', '0.1mm'), ('0.2mm', '0.2mm'), ('0.5mm', '0.5mm'),
    ('0.8mm', '0.8mm'), ('1mm', '1mm'), ('1.5mm', '1.5mm'),
    ('2mm', '2mm'), ('4mm', '4mm'), ('6mm', '6mm'), ('9mm', '9mm'),
    ('others', 'Others')
]


# Core Farm Models
class Farm(models.Model):  # Represents a catfish farm linked to a company
    name = models.CharField(max_length=255, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="catfish_farms")
    location = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Check if this is a new farm

        super().save(*args, **kwargs)  # Save the farm first to get an ID

        if is_new:  # Only create a Branch if this is a new Farm
            Branch.objects.get_or_create(
                branch_id=self.id,  # Now self.id is available
                defaults={
                    "name": self.name,
                    "company": self.company,
                    "appName": "catFishFarm",
                    "modelName": "Farm",
                    "created_at": self.created_at,
                    "location": self.location,
                }
            )


    def __str__(self):
        return self.name


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

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="catfishfarm_staff_members")
    leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name="catfishfarm_staff_member_lead", null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="catfishfarm_staff_members")
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="staff_members")
    position = models.CharField(max_length=20, choices=POSITION_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    level = models.IntegerField(choices=LEVEL_CHOICES, default=1)  # New level field
    assigned_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="catfishfarm_created_staff_assignments", null=True)

    # class Meta:
    #     unique_together = ('user', 'farm', 'company', 'status')  # Ensure no duplicates for user, farm, company, and status

    class Meta:
        indexes = [
            models.Index(fields=["company", "farm"]),  # ✅ Add compound index
        ]

    def __str__(self):
        return f"{self.user.username} - {self.position} at {self.farm.name} ({self.status}, Level {self.level})"
    

class FarmOwnership(models.Model):  # Tracks ownership percentages of a farm
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="owners")
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    ownership_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Ownership percentage")

    def __str__(self):
        return f"{self.owner.username} owns {self.ownership_percentage}% of {self.farm.name}"


class Pond(models.Model):  # Represents a pond within a farm
    depth = models.DecimalField(max_digits=10, decimal_places=2, help_text="Depth in meters")
    TYPE_CHOICES = [
        ('Earthen', 'Earthen'),
        ('Concrete', 'Concrete'),
        ('Tarpaulin', 'Tarpaulin')
    ]
    
    name = models.CharField(max_length=255)
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="ponds")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    size = models.DecimalField(max_digits=10, decimal_places=2, help_text="Size in square meters")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.type})"


class PondCondition(models.Model):  # Logs water quality parameters of a pond
    pond = models.ForeignKey(Pond, on_delete=models.CASCADE, related_name="conditions")
    recorded_at = models.DateTimeField(auto_now_add=True)
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Temperature in Celsius")
    ph_level = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="pH level")
    ammonia_level = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Ammonia concentration")

    def __str__(self):
        return f"Condition recorded for {self.pond.name} at {self.recorded_at}"


class Batch(models.Model):  # Represents a batch of fish in a farm
    name = models.CharField(max_length=255)
    species = models.CharField(max_length=255)
    source = models.CharField(max_length=255, help_text="Hatchery or supplier")
    stocking_date = models.DateField()
    initial_quantity = models.PositiveIntegerField()
    initial_avg_weight = models.DecimalField(max_digits=5, decimal_places=2, help_text="Initial weight in grams")
    status = models.CharField(max_length=20, choices=[('Stocked', 'Stocked'), ('Harvested', 'Harvested')], default='Stocked')

    def __str__(self):
        return f"{self.name} - {self.species} ({self.status})"


class BatchMovement(models.Model):  # Tracks batch transfers between ponds
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="movements")
    from_pond = models.ForeignKey(Pond, on_delete=models.CASCADE, related_name="batch_moved_out", null=True, blank=True)
    to_pond = models.ForeignKey(Pond, on_delete=models.CASCADE, related_name="batch_moved_in")
    moved_on = models.DateField()

    def __str__(self):
        return f"{self.batch.name} moved from {self.from_pond} to {self.to_pond} on {self.moved_on}"


class FeedInventory(models.Model):  # Manages feed stock and size tracking
    feed_type = models.CharField(max_length=255)
    quantity_in_kg = models.DecimalField(max_digits=10, decimal_places=2)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.feed_type}: {self.quantity_in_kg} kg available"


class StockingHistory(models.Model):  # Logs when fish batches are stocked in ponds
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="stocking_history")
    stocked_at = models.DateField()
    pond = models.ForeignKey(Pond, on_delete=models.CASCADE, related_name="stocking_history")
    quantity = models.PositiveIntegerField()
    weight = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total weight stocked")


class DestockingHistory(models.Model):  # Tracks fish removals for sales or sorting
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="destocking_history")
    pond = models.ForeignKey(Pond, on_delete=models.CASCADE, related_name="destocking_history")
    quantity = models.PositiveIntegerField()
    weight = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total weight removed")
    reason = models.CharField(max_length=255, choices=[('Sale', 'Sale'), ('Sorting', 'Sorting')], help_text="Reason for destocking")
    destocked_at = models.DateField()


class StaffTaskAssignment(models.Model):  # Assigns and tracks staff tasks
    staff = models.ForeignKey(StaffMember, on_delete=models.CASCADE, related_name="assigned_tasks")
    task = models.CharField(max_length=255)
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.task} assigned to {self.staff.user.username}"
    

class Category(models.Model):  # Supports hierarchical categories (e.g., Security → Dogs)
    name = models.CharField(max_length=255, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subcategories')
    
    def __str__(self):
        return self.name




# BenefactorItem subclasses


class BenefactorItem(models.Model):  
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="benefactor_items")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class DogItem(BenefactorItem):  
    breed = models.CharField(max_length=255)
    age = models.PositiveIntegerField(help_text="Age in years")
    vaccinated = models.BooleanField(default=False)
    health_status = models.TextField(blank=True, null=True)

class CCTVItem(BenefactorItem):  
    brand = models.CharField(max_length=255)
    resolution = models.CharField(max_length=50, help_text="Resolution (e.g., 1080p, 4K)")
    storage_capacity = models.CharField(max_length=50, help_text="Storage capacity in TB")

class GeneratorItem(BenefactorItem):  
    brand = models.CharField(max_length=255)
    power_output = models.CharField(max_length=50, help_text="Power output (e.g., 5kVA)")
    fuel_type = models.CharField(max_length=50, choices=[('Diesel', 'Diesel'), ('Petrol', 'Petrol')])



# Financial & Sales Models

class Sales(models.Model):  # Records fish sales transactions
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="sales")
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name="purchases")
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE, related_name="sales")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit sold")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total price (calculated automatically)")
    sale_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure total price is calculated correctly
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale of {self.quantity} from {self.batch.name} to {self.customer.name}"



class Customer(models.Model):  # Stores customer details
    name = models.CharField(max_length=255)
    contact = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Invoice(models.Model):  # Generates invoices for sales
    sales = models.ForeignKey(Sales, on_delete=models.CASCADE, related_name="invoices")
    invoice_number = models.CharField(max_length=50, unique=True)
    issued_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Paid', 'Paid')])

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.status}"


class Payment(models.Model):  # Tracks customer payments
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=[('Cash', 'Cash'), ('Bank Transfer', 'Bank Transfer'), ('Mobile Payment', 'Mobile Payment')])
    payment_date = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure payment does not exceed invoice total
        total_payments = sum(payment.amount_paid for payment in self.invoice.payments.all()) + self.amount_paid
        invoice_total = self.invoice.sales.total_price

        if total_payments > invoice_total:
            raise ValueError("Total payments cannot exceed the invoice total")
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payment of {self.amount_paid} for {self.invoice.invoice_number}"



class ContractorVendor(models.Model):  # Stores vendor details and approved supplies/services
    name = models.CharField(max_length=255)
    contact = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    approved_items = models.ManyToManyField(BenefactorItem, related_name="vendors", blank=True)
    services = models.TextField(blank=True, null=True, help_text="Services provided by the vendor (e.g., logistics, maintenance)")
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True, help_text="Vendor rating out of 5")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Expense(models.Model):  # Tracks farm expenses
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="expenses")
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name="expenses")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total expense amount")
    description = models.TextField(blank=True, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Expense {self.amount} for {self.category.name} at {self.farm.name}"


class ExpenseBreakdown(models.Model):  # Tracks sub-expenses like logistics, delivery fees, agent payments
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="breakdowns")
    payee_type = models.CharField(max_length=20, choices=[('Vendor', 'Vendor'), ('Staff', 'Staff'), ('Agent', 'Agent')])
    payee_vendor = models.ForeignKey('ContractorVendor', on_delete=models.SET_NULL, null=True, blank=True, related_name="expense_payments")
    payee_staff = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_expense_payments")
    description = models.CharField(max_length=255, help_text="Purpose of this breakdown (e.g., Delivery fee, Logistics)")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount for this particular breakdown")
    recorded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Ensure total breakdown amount does not exceed main expense amount
        existing_breakdowns = ExpenseBreakdown.objects.filter(expense=self.expense).exclude(id=self.id)
        total_breakdown = sum(b.amount for b in existing_breakdowns) + self.amount
        if total_breakdown > self.expense.amount:
            raise ValueError("Total breakdown cost cannot exceed the main expense amount")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description}: {self.amount} for {self.payee_type}"




class ExpenseAllocation(models.Model):  # Allocates expenses to BenefactorItems
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="allocations")
    benefactor_item = models.ForeignKey(BenefactorItem, on_delete=models.CASCADE, related_name="expense_allocations")
    percentage_share = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage of expense allocated")

    def save(self, *args, **kwargs):
        # Ensure the total percentage for an expense does not exceed 100%
        existing_allocations = ExpenseAllocation.objects.filter(expense=self.expense).exclude(id=self.id)
        total_percentage = sum(allocation.percentage_share for allocation in existing_allocations) + self.percentage_share
        if total_percentage > 100:
            raise ValueError("Total expense allocation cannot exceed 100%")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.percentage_share}% of {self.expense.amount} allocated to {self.benefactor_item.name}"
    

#  Tracking & Analytics Models 

class TaskChecklist(models.Model):  # Checklist for task completion (ensures validation)
    task = models.ForeignKey(CompanyTask, on_delete=models.CASCADE, related_name="checklist")
    item = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.item} - {'Completed' if self.is_completed else 'Pending'}"


class FishGrowth(models.Model):  # Logs growth rate, feed intake, and conversion rate per pond over a specific period
    pond = models.ForeignKey('Pond', on_delete=models.CASCADE, related_name="growth_records")
    start_date = models.DateField(help_text="Start date of the growth tracking period")
    end_date = models.DateField(help_text="End date of the growth tracking period")
    total_feed_bags = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total feed bags consumed during the period")
    weight_before = models.DecimalField(max_digits=10, decimal_places=2, help_text="Weight per fish at start in grams")
    weight_after = models.DecimalField(max_digits=10, decimal_places=2, help_text="Weight per fish at end in grams")
    fcr = models.DecimalField(max_digits=5, decimal_places=2, help_text="Feed Conversion Ratio (FCR)")

    def __str__(self):
        return f"Growth record for {self.pond.name} from {self.start_date} to {self.end_date}"



class FeedStock(models.Model):  # Tracks feed purchases, usage per pond, and shortages
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="feed_stock")
    feed_type = models.CharField(max_length=255)
    FEED_SIZE_CHOICES = [
        ('0.1mm', '0.1mm'),
        ('0.2mm', '0.2mm'),
        ('0.5mm', '0.5mm'),
        ('0.8mm', '0.8mm'),
        ('1mm', '1mm'),
        ('1.5mm', '1.5mm'),
        ('2mm', '2mm'),
        ('4mm', '4mm'),
        ('6mm', '6mm'),
        ('9mm', '9mm'),
        ('others', 'Others')
    ]
    feed_size = models.CharField(max_length=10, choices=FEED_SIZE_CHOICES, default='others', help_text="Size of feed in stock")
    vendor = models.ForeignKey('ContractorVendor', on_delete=models.SET_NULL, null=True, blank=True, related_name="feed_supplies")
    initial_quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total quantity purchased")
    quantity_in_kg = models.DecimalField(max_digits=10, decimal_places=2, help_text="Current available quantity")
    expiry_date = models.DateField(null=True, blank=True, help_text="Expiry date of the feed (if applicable)")
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.feed_type} ({self.feed_size}) - {self.quantity_in_kg} kg available"



class FeedConsumption(models.Model):  # Logs feed given per session per pond (alerts for abnormal usage)
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="feed_consumption")
    pond = models.ForeignKey('Pond', on_delete=models.CASCADE, related_name="feed_consumption")
    recorded_at = models.DateTimeField(auto_now_add=True)
    feed_type = models.CharField(max_length=255)
    FEED_SIZE_CHOICES = [
        ('0.1mm', '0.1mm'),
        ('0.2mm', '0.2mm'),
        ('0.5mm', '0.5mm'),
        ('0.8mm', '0.8mm'),
        ('1mm', '1mm'),
        ('1.5mm', '1.5mm'),
        ('2mm', '2mm'),
        ('4mm', '4mm'),
        ('6mm', '6mm'),
        ('9mm', '9mm'),
        ('others', 'Others')
    ]
    feed_size = models.CharField(max_length=10, choices=FEED_SIZE_CHOICES, default='others', help_text="Size of feed used")
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} kg of {self.feed_type} ({self.feed_size}) fed to {self.pond.name}"



class HealthLog(models.Model):  # Tracks fish health observations, symptoms, and treatment actions
    pond = models.ForeignKey('Pond', on_delete=models.CASCADE, related_name="health_logs")
    recorded_at = models.DateTimeField(auto_now_add=True)
    symptoms = models.TextField()
    treatment = models.TextField(blank=True, null=True)
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="Date when health issue was resolved")
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Resolved', 'Resolved')], default='Pending')

    def __str__(self):
        return f"Health log for {self.pond.name} on {self.recorded_at} (Resolved: {self.resolved_at if self.resolved_at else 'Pending'})"



class MortalityLog(models.Model):  # Records fish deaths, causes, and corrective measures
    batch = models.ForeignKey('Batch', on_delete=models.CASCADE, related_name="mortality_logs")
    pond = models.ForeignKey('Pond', on_delete=models.CASCADE, related_name="mortality_logs")
    recorded_at = models.DateField()
    quantity = models.PositiveIntegerField()
    cause = models.CharField(max_length=255)
    corrective_action = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.quantity} fish lost in {self.pond.name} from {self.batch.name} due to {self.cause}"



class MarketPrice(models.Model):  # Stores local fish price trends based on fish size categories
    location = models.CharField(max_length=255)
    recorded_at = models.DateField()
    fish_per_kg = models.PositiveIntegerField(help_text="Number of fish making up 1 kg")
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price for 1 kg of fish at this size category")

    def __str__(self):
        return f"Market price at {self.location}: {self.price_per_kg} per kg for {self.fish_per_kg} fish per kg"



class ProfitAnalysis(models.Model):  # Calculates profit/loss based on expenses vs sales
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="profit_analysis")
    recorded_at = models.DateField()
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2)
    total_expenses = models.DecimalField(max_digits=15, decimal_places=2)
    profit_or_loss = models.DecimalField(max_digits=15, decimal_places=2, help_text="Positive for profit, negative for loss")

    def __str__(self):
        return f"Profit analysis for {self.farm.name} on {self.recorded_at}"



# Alerts & AI Insights (Future-Ready)
class Alert(models.Model):  # Triggers notifications for issues (missed tasks, abnormal feeding, high mortality)
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="alerts")
    category = models.CharField(max_length=255, help_text="Type of alert (e.g., Task Missed, Abnormal Feeding, High Mortality)")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Alert for {self.farm.name}: {self.category} - {'Resolved' if self.resolved else 'Pending'}"


class AIInsights(models.Model):  # Stores AI-generated insights on growth, health, and profitability predictions
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="ai_insights")
    insight_type = models.CharField(max_length=255, help_text="Type of AI insight (e.g., Growth Prediction, Health Risk, Profit Forecast)")
    insight_details = models.TextField()
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AI Insight for {self.farm.name}: {self.insight_type}"


class IoTData(models.Model):  # Stores multi-sensor readings for farms
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="iot_data")
    data = models.JSONField(help_text="Stores multiple sensor readings like temperature, pH, ammonia")
    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"IoT Data for {self.farm.name} recorded on {self.recorded_at}"
    

class Report(models.Model):  # Stores automated farm reports (weekly/monthly summaries)
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, related_name="reports")
    report_type = models.CharField(max_length=255, help_text="Type of report (e.g., Weekly Summary, Monthly Profit Analysis)")
    generated_at = models.DateTimeField(auto_now_add=True)
    content = models.TextField(help_text="Report details")

    def __str__(self):
        return f"{self.report_type} for {self.farm.name} generated on {self.generated_at}"
