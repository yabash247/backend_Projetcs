

from rest_framework import serializers
from .models import Farm, StaffMember
from company.models import Company
from company.utils import has_permission
from rest_framework.exceptions import PermissionDenied


class FarmSerializer(serializers.ModelSerializer):
    creatorId = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Farm
        fields = '__all__'

    def update(self, instance, validated_data):
        # Handle `established_date`: Use existing value if not provided
        if 'established_date' not in validated_data:
            validated_data['established_date'] = instance.established_date

        # Handle `company`: Only allow if user has permission for the target company
        if 'company' in validated_data:
            target_company = validated_data['company']
            user = self.context['request'].user

            # Ensure user has permission for the target company
            if not has_permission(user=user, company=target_company, model_name="Farm", action="PUT"):
                raise PermissionDenied("You do not have permission to assign this farm to the selected company.")

        # Update all fields as usual
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.full_clean()  # Validate instance before saving
        instance.save()
        return instance


class StaffMemberSerializer(serializers.ModelSerializer):
    created_by = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = StaffMember
        fields = '__all__'

    def validate(self, data):
        # Validate the assigned user is a staff member of the company
        user = data.get('user', self.instance.user if self.instance else None)
        company = data.get('company', self.instance.company if self.instance else None)
        farm = data.get('farm', self.instance.farm if self.instance else None)

        if not user.is_staff:
            raise serializers.ValidationError("The assigned user must be a staff member of the company.")

        # Check if the user is associated with the company
        if not user.company_set.filter(id=company.id).exists():
            raise serializers.ValidationError("The assigned user is not a staff member of this company.")

        # Ensure the farm belongs to the company
        if farm.company.id != company.id:
            raise serializers.ValidationError("The farm does not belong to the specified company.")

        return data

    def update(self, instance, validated_data):
        # Check if the new request matches the current farm, company, and status
        new_farm = validated_data.get('farm', instance.farm)
        new_company = validated_data.get('company', instance.company)
        new_status = validated_data.get('status', instance.status)

        # If farm, company, and status are the same, set the previous status to inactive
        if new_farm == instance.farm and new_company == instance.company and new_status == instance.status:
            instance.status = 'inactive'

        # Update other fields with new values
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
