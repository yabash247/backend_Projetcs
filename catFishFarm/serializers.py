from company.models import Media as CompanyMedia
from rest_framework import serializers
from .models import Farm, Pond, Batch, BatchMovement, StockingHistory, DestockingHistory, StaffMember
from company.utils import has_permission
from django.core.exceptions import PermissionDenied
from company.models import Company

FEED_SIZE_CHOICES = [
    ('0.1mm', '0.1mm'), ('0.2mm', '0.2mm'), ('0.5mm', '0.5mm'),
    ('0.8mm', '0.8mm'), ('1mm', '1mm'), ('1.5mm', '1.5mm'),
    ('2mm', '2mm'), ('4mm', '4mm'), ('6mm', '6mm'), ('9mm', '9mm'),
    ('others', 'Others')
]

# Farm Serializer
class FarmSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)  # Make 'name' optional
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all(), required=False)  # Make 'company' optional

    class Meta:
        model = Farm
        fields = '__all__'
        read_only_fields = ['created_by']  # Ensure this is auto-set

    def validate(self, data):
        # Use existing `company` during updates if it's not provided
        if self.instance and "company" not in data:
            data["company"] = self.instance.company

        # Use existing `name` during updates if it's not provided
        if self.instance and "name" not in data:
            data["name"] = self.instance.name

        return data
    
    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        company_id = validated_data.get('company')

        # Validate company
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise PermissionDenied("Invalid company provided.")

        # Ensure user has permission to create a farm in the given company
        if not has_permission(user, company, 'catFishFarm', 'Farm', 'add'):
            raise PermissionDenied("You do not have permission to create farms in this company.")

        validated_data['created_by'] = user
        validated_data['company'] = company
        return super().create(validated_data)

   
class StaffMemberSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    leader_username = serializers.CharField(source="leader.username", read_only=True)


    class Meta:
        model = StaffMember
        fields = [
            'id', 'user', 'user_username', 'leader', 'leader_username',
            'company', 'farm', 'position', 'status', 'level', 'assigned_at', 'created_by'
        ]
        read_only_fields = ['created_by', 'assigned_at']

    def create(self, validated_data):
        request = self.context['request']
        user = request.user
        validated_data['created_by'] = user
        return super().create(validated_data)


class PondSerializer(serializers.ModelSerializer):  # Handles Pond serialization
    class Meta:
        model = Pond
        fields = '__all__'


from .models import PondMaintenanceLog
class PondMaintenanceLogSerializer(serializers.ModelSerializer):
    pond_name = serializers.CharField(source="pond.name", read_only=True)
    performed_by_name = serializers.CharField(source="performed_by.username", read_only=True)

    class Meta:
        model = PondMaintenanceLog
        fields = [
            'id', 'pond', 'pond_name', 'date', 'maintenance_type', 
            'description', 'performed_by', 'performed_by_name'
        ]
        read_only_fields = ['date', 'performed_by']
    
    def create(self, validated_data):
        request = self.context['request']
        validated_data['performed_by'] = request.user  # Auto-assign the user
        return super().create(validated_data)


class BatchSerializer(serializers.ModelSerializer):  # Handles Batch serialization
    class Meta:
        model = Batch
        fields = '__all__'


class BatchMovementSerializer(serializers.ModelSerializer):  # Handles Batch Movement serialization
    class Meta:
        model = BatchMovement
        fields = '__all__'


class StockingHistorySerializer(serializers.ModelSerializer):  # Handles Stocking History serialization
    class Meta:
        model = StockingHistory
        fields = '__all__'


class DestockingHistorySerializer(serializers.ModelSerializer):  # Handles Destocking History serialization
    class Meta:
        model = DestockingHistory
        fields = '__all__'

