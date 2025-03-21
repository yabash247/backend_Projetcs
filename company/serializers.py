from rest_framework import serializers
from .models import Company, Authority, Staff, StaffLevels, Branch, Task, Media
from django.apps import apps
from django.db.models import Q
from users.models import User  # Import the User model

class BranchSerializer(serializers.ModelSerializer):
    associated_data = serializers.SerializerMethodField()
    #appName = serializers.CharField(source='app_name')

    class Meta:
        model = Branch
        fields = ['id', 'name', 'company', 'branch_id', 'status', 'appName', 'modelName', 'created_at', 'associated_data']

    def get_associated_data(self, obj):
        """
        Dynamically fetch the associated model information.
        """
        try:
            # Dynamically load the model class
            model_class = apps.get_model(app_label=obj.appName, model_name=obj.modelName)

            # Fetch the associated instance using branch_id
            associated_instance = model_class.objects.get(id=obj.branch_id)

            # Serialize the associated instance
            if hasattr(associated_instance, 'to_dict'):
                # If the model has a `to_dict` method, use it
                return associated_instance.to_dict()
            else:
                # If not, serialize a subset of its fields manually
                return {
                    'id': associated_instance.id,
                    'name': getattr(associated_instance, 'name', None),
                    'status': getattr(associated_instance, 'status', None),
                    'created_at': getattr(associated_instance, 'created_at', None),
                }
        except Exception as e:
            # Return an error message if fetching fails
            return {"error": str(e)}



class StaffLevelsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffLevels
        fields = '__all__'
        read_only_fields = ['id', 'user ', 'company ']


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer to return full user details instead of just user ID.
    """
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]

class StaffSerializer(serializers.ModelSerializer):
    """
    Serializer for the Staff model.
    """
    user = UserSerializer(read_only=True)  # ✅ Returns full user details instead of just an ID
    added_by = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = [
            "id", "user", "company", "work_phone", "work_email", "date_created",
            "joined_company_date", "comments", "added_by", "approved_by"
        ]


class AuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Authority
        fields = [
            'id', 'model_name', 'app_name', 'company', 'requested_by', 'approver',
            'view', 'add', 'edit', 'delete', 'accept', 'approve', 'created'
        ]
        read_only_fields = ['id', 'created', 'requested_by']

    def validate(self, data):
        """
        Validate the app_name and model_name combination.
        """
        app_name = data.get('app_name')
        model_name = data.get('model_name')

        # Check if app_name exists
        try:
            app_config = apps.get_app_config(app_name)
        except LookupError:
            raise serializers.ValidationError(f"The app '{app_name}' does not exist.")

        # Check if model_name exists in the specified app
        if not hasattr(app_config, 'get_model') or not app_config.get_model(model_name, require_ready=False):
            raise serializers.ValidationError(
                f"The model '{model_name}' does not exist in the app '{app_name}'."
            )

        # Ensure unique combination of model_name, app_name, and company
        company = data.get('company')
        if not self.instance and Authority.objects.filter(company=company, app_name=app_name, model_name=model_name).exists():
            raise serializers.ValidationError(
                f"The model '{app_name}.{model_name}' is already defined for this company."
            )

        return data


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'description', 'creator', 'approver', 'phone', 'email', 'website', 'comments', 'status']
        read_only_fields = ['id', 'creator']  # Creator is set automatically in the view

class AdminCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'description', 'creator', 'approver', 'phone', 'email', 'website', 'comments', 'status']
        read_only_fields = ['id', 'creator']


class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = "__all__"
        read_only_fields = ["id", "created_date", "negative_flags_count"]

    def validate(self, data):
        """
        Validate Media input.
        """
        app_name = data.get("app_name")
        branch = data.get("branch")
        company = data.get("company")

        # Ensure branch is not provided if app_name == "company"
        if app_name == "company" and branch is not None:
            raise serializers.ValidationError({"branch": "Branch cannot be specified for the 'company' app."})

        # Validate model existence (optional logic based on your use case)
        # Example: Check if the provided model_id exists in the specified model

        return data

    def create(self, validated_data):
        """
        Override to suggest titles and categories based on user input and past data.
        """
        media_instance = super().create(validated_data)

        # Generate suggestions for title or category (Optional: implement based on your logic)
        # Example: Query past inputs from this model for suggestions

        return media_instance


class TaskSerializer(serializers.ModelSerializer):
    assignedToUserId = serializers.IntegerField(source="assigned_to.id", read_only=True)  # ✅ Ensures assigned user ID is returned

    class Meta:
        model = Task
        fields = ["id", "title", "due_date", "status", "assignedToUserId"]
        #fields = "__all__"
        #read_only_fields = ['id', 'created_at']


    
  
from .models import ActivityOwner
class ActivityOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityOwner
        fields = '__all__'
        #read_only_fields = ['id', 'user', 'company']

'''

from .models import RewardsPointsTracker
class RewardsPointsTrackerSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    branch_name = serializers.SerializerMethodField()
    task_title = serializers.SerializerMethodField()

    class Meta:
        model = RewardsPointsTracker
        fields = [
            'id',
            'user',
            'user_name',
            'company',
            'company_name',
            'branch',
            'branch_name',
            'task',
            'task_title',
            'transaction_type',
            'credit',
            'blocked',
            'credit_date',
            'point_conversion_rate',
            'debit',
            'debit_date',
            'debit_requested_by',
            'debit_approved_by',
            'comments',
            'points_available',
            'points_pending',
            'updated_at',
        ]
        read_only_fields = ['points_available', 'points_pending', 'updated_at']

    def get_user_name(self, obj):
        """Retrieve the user's full name or username."""
        return obj.user.get_full_name() or obj.user.username

    def get_company_name(self, obj):
        """Retrieve the company name."""
        return obj.company.name if obj.company else None

    def get_branch_name(self, obj):
        """Retrieve the branch name."""
        return obj.branch.name if obj.branch else None

    def get_task_title(self, obj):
        """Retrieve the task title."""
        return obj.task.title if obj.task else None

    def validate(self, data):
        """
        Custom validation for the rewards points transaction.
        Ensures that credits, debits, and blocked points are non-negative.
        """
        if data.get('credit', 0) < 0:
            raise serializers.ValidationError({"credit": "Credit points cannot be negative."})
        if data.get('debit', 0) < 0:
            raise serializers.ValidationError({"debit": "Debit points cannot be negative."})
        if data.get('blocked', 0) < 0:
            raise serializers.ValidationError({"blocked": "Blocked points cannot be negative."})
        return data

'''