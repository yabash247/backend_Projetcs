

from rest_framework import serializers
from .models import Farm, StaffMember
from company.models import Company
from company.models import Staff
from users.models import User
from company.utils import has_permission
from rest_framework.exceptions import PermissionDenied, ValidationError
from company.serializers import CompanySerializer # Import the CompanySerializer for nested serialization


class FarmSerializer(serializers.ModelSerializer):
    associated_company = serializers.SerializerMethodField()

    class Meta:
        model = Farm
        fields = [
            'id',
            'name',
            'description',
            'profile_image',
            'background_image',
            'established_date',
            'status',
            'creatorId',
            'associated_company',  # Include associated company details
        ]

    def get_associated_company(self, obj):
        """
        Fetch the company details if a companyID is provided.
        """
        company_id = self.context.get('companyID')
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
                return CompanySerializer(company).data
            except Company.DoesNotExist:
                return None
        return None
    
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
        """
        Perform validation on the data before saving.
        """
        # Extract data fields
        user = data.get('user', self.instance.user if self.instance else None)
        company = data.get('company', self.instance.company if self.instance else None)
        farm = data.get('farm', self.instance.farm if self.instance else None)
        position = data.get('position', self.instance.position if self.instance else None)
        level = data.get('level', self.instance.level if self.instance else None)
        status = data.get('status', self.instance.status if self.instance else 'active')

        # 1. Check if the user is valid
        if not User.objects.filter(id=user.id).exists():
            raise ValidationError({"user": "The specified user does not exist."})

        # 2. Check if the user is a staff member of the company
        if not Staff.objects.filter(user=user, company=company).exists():
            raise ValidationError({"user": "The specified user is not a staff member of the company."})

        # 3. Check if the company is valid
        if not Company.objects.filter(id=company.id).exists():
            raise ValidationError({"company": "The specified company does not exist."})

        # 4. Check if the farm is valid
        if not Farm.objects.filter(id=farm.id).exists():
            raise ValidationError({"farm": "The specified farm does not exist."})

        # 5. Check if the farm belongs to the company
        if farm.company_id != company.id:
            raise ValidationError({"farm": "The specified farm does not belong to the company."})

        # 6. Check for duplicate active entries
        duplicate_active = StaffMember.objects.filter(
            user=user,
            company=company,
            farm=farm,
            position=position,
            level=level,
            status='active'
        )
        if duplicate_active.exists():
            raise ValidationError({
                "detail": "A staff member with the same user, company, farm, position, level, and active status already exists."
            })

        return data

    def create(self, validated_data):
        """
        Handle the creation of a new StaffMember instance.
        """
        user = validated_data.get('user')
        company = validated_data.get('company')
        farm = validated_data.get('farm')
        position = validated_data.get('position')
        level = validated_data.get('level')

        # 7. Handle case where user exists with different position/level
        existing_staff = StaffMember.objects.filter(user=user, company=company, farm=farm, status='active').exclude(
            position=position, level=level
        )

        if existing_staff.exists():
            # Deactivate existing staff members
            existing_staff.update(status='inactive')

        # Save the new instance
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Handle updates to an existing StaffMember instance.
        """
        user = validated_data.get('user', instance.user)
        company = validated_data.get('company', instance.company)
        farm = validated_data.get('farm', instance.farm)
        position = validated_data.get('position', instance.position)
        level = validated_data.get('level', instance.level)

        # Check if the new data matches an existing active entry
        duplicate_active = StaffMember.objects.filter(
            user=user,
            company=company,
            farm=farm,
            position=position,
            level=level,
            status='active'
        ).exclude(pk=instance.pk)

        if duplicate_active.exists():
            raise ValidationError({
                "detail": "A staff member with the same user, company, farm, position, level, and active status already exists."
            })

        # Handle case where existing entries need to be deactivated
        existing_staff = StaffMember.objects.filter(user=user, company=company, farm=farm, status='active').exclude(
            position=position, level=level
        )

        if existing_staff.exists():
            # Deactivate existing staff members
            existing_staff.update(status='inactive')

        # Update instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance




