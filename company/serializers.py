from rest_framework import serializers
from .models import Company, Authority, Staff, StaffLevels, Branch
from django.apps import apps

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

    

class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = [
            'id', 'user', 'company', 'work_phone', 'work_email',
            'date_created', 'joined_company_date', 'comments', 'added_by', 'approved_by'
        ]
        read_only_fields = ['id', 'date_created', 'added_by']

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