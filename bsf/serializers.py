

from rest_framework import serializers
from .models import Farm, StaffMember, Net, Batch, DurationSettings, NetUseStats, Pond, PondUseStats
from company.models import Company, Staff, Media
from users.models import User
from company.utils import has_permission
from rest_framework.exceptions import PermissionDenied, ValidationError
from company.serializers import CompanySerializer, MediaSerializer # Import the CompanySerializer for nested serialization


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


class NetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Net
        fields = ['id', 'name', 'length', 'width', 'height', 'status', 'created_at', 'company', 'farm']
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        """
        Custom validation to ensure the Net's dimensions are positive and the farm belongs to the company.
        """
        company = data.get('company')
        farm = data.get('farm')

        # Validate positive dimensions
        for field in ['length', 'width', 'height']:
            if data.get(field) is not None and data[field] <= 0:
                raise serializers.ValidationError({field: f"{field.capitalize()} must be greater than zero."})

        # Check if the farm belongs to the company
        if farm and company and farm.company != company:
            raise serializers.ValidationError({"farm": "The specified farm does not belong to the provided company."})

        return data

    def update(self, instance, validated_data):
        """
        Override update to use existing data for missing fields.
        """
        for attr, value in validated_data.items():
            setattr(instance, attr, value if value is not None else getattr(instance, attr))
        instance.save()
        return instance



class BatchSerializer(serializers.ModelSerializer):
    associated_media = serializers.SerializerMethodField()
    duration_settings = serializers.SerializerMethodField()

    class Meta:
        model = Batch
        fields = "__all__"
        read_only_fields = ["batch_name", "created_at"]

    def get_associated_media(self, obj):
        """
        Fetch associated media using model_id and app_name.
        """
        media = Media.objects.filter(app_name="bsf", model_name="Batch", model_id=obj.id)
        return MediaSerializer(media, many=True).data

    def get_duration_settings(self, obj):
        """
        Fetch associated DurationSettings based on the batch's farm and company.
        """
        try:
            duration_settings = DurationSettings.objects.get(company=obj.company, farm=obj.farm)
        except DurationSettings.DoesNotExist:
            duration_settings = DurationSettings.objects.filter(id=1).first()  # Fallback to default
        return DurationSettingsSerializer(duration_settings).data if duration_settings else None

    def validate(self, data):
        """
        Ensure valid batch data.
        """
        if "laying_start_date" in data and "laying_end_date" in data:
            if data["laying_start_date"] > data["laying_end_date"]:
                raise serializers.ValidationError("Laying start date cannot be after the end date.")

        if "incubation_start_date" in data and "incubation_end_date" in data:
            if data["incubation_start_date"] > data["incubation_end_date"]:
                raise serializers.ValidationError("Incubation start date cannot be after the end date.")

        return data



class DurationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DurationSettings
        fields = '__all__'

    def create(self, validated_data):
        company = validated_data.get("company")
        farm = validated_data.get("farm")

        # Use default ID if the farm has no data
        if not DurationSettings.objects.filter(company=company, farm=farm).exists():
            instance, created = DurationSettings.objects.get_or_create(company=company, farm=farm, defaults=validated_data)
            if not created:
                raise serializers.ValidationError("DurationSettings already exist for this farm.")
            return instance
        
        return super().create(validated_data)




class NetUseStatsSerializer(serializers.ModelSerializer):
    media = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False, use_url=False), required=False, write_only=True
    )

    class Meta:
        model = NetUseStats
        fields = "__all__"

    def validate(self, data):
        net = data.get("net")
        stats = NetUseStats.objects.filter(net=net, stats="ongoing").first()

        if stats:
            batch = stats.batch
            raise serializers.ValidationError(
                f"The specified net is still in use by Batch '{batch.batch_name}' (ID: {batch.id})."
            )

        if data.get("lay_end") and not data.get("harvest_weight"):
            raise serializers.ValidationError("Harvest weight is required if 'lay_end' is provided.")

        return data

    def create(self, validated_data):
        
        media_files = validated_data.pop("media", [])
        net_use_stats = super().create(validated_data)

        # Save media files if provided
        for media_file in media_files:
            Media.objects.create(
                company=net_use_stats.company,
                branch=None,
                app_name="bsf",
                model_name="NetUseStats",
                model_id=net_use_stats.id,
                file=media_file,
                title=f"NetUseStats Media for {net_use_stats.net.name}",
                category="Net Stats Media",
                uploaded_by=validated_data["created_by"],
                status="active",
            )

        return net_use_stats

    def update(self, instance, validated_data):
        media_files = validated_data.pop("media", [])
        updated_instance = super().update(instance, validated_data)

        # Save media files if provided
        for media_file in media_files:
            Media.objects.create(
                company=updated_instance.company,
                branch=None,
                app_name="bsf",
                model_name="NetUseStats",
                model_id=updated_instance.id,
                file=media_file,
                title=f"NetUseStats Media for {updated_instance.net.name}",
                category="Net Stats Media",
                uploaded_by=validated_data["created_by"],
                status="active",
            )

        return updated_instance



class PondSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pond
        fields = "__all__"


class MediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Media
        fields = "__all__"



class PondUseStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PondUseStats
        fields = "__all__"


