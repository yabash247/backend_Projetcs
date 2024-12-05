# views.py
from rest_framework import generics, permissions, status
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import Farm, StaffMember, Net, Batch, DurationSettings, NetUseStats
from company.models import Company, Media  # Import the Company model
from company.serializers import MediaSerializer
from .serializers import FarmSerializer, StaffMemberSerializer, NetSerializer, BatchSerializer, DurationSettingsSerializer, NetUseStatsSerializer
from rest_framework.permissions import BasePermission, IsAuthenticated
from company.utils import has_permission, check_user_exists
#from company.views import has_permission
from django.shortcuts import get_object_or_404



import logging


class IsStaffPermission(permissions.BasePermission):
    """
    Custom permission to allow only staff users with the required permissions.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # For detail views (e.g., PUT, DELETE), get the company from the farm instance
        if "pk" in view.kwargs:
            farm_id = view.kwargs.get("pk")
            try:
                farm = Farm.objects.get(id=farm_id)
                company = farm.company
            except Farm.DoesNotExist:
                raise PermissionDenied("Farm does not exist.")
        else:
            # For list or create views
            company_id = request.data.get("company") or request.query_params.get("company")
            if not company_id:
                raise PermissionDenied("Company ID must be provided.")
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                raise PermissionDenied("Invalid Company ID.")

        # Validate permissions
        model_name = "Farm"
        action = request.method
        if not has_permission(user=request.user, company=company, model_name=model_name, action=action):
            raise PermissionDenied("You do not have permission to perform this action.")
        return True


class IsAuthenticatedAndHasPermissionOrSelf(BasePermission):
    """
    Allows access to authenticated users with permission or to their own StaffMember data.
    """
    def has_object_permission(self, request, view, obj):
        # Allow access if the requester is viewing their own staff member data
        if obj.user == request.user:
            return True

        # Otherwise, check permissions for the associated company
        return has_permission(user=request.user, company=obj.company, model_name="StaffMember", action=request.method)

    def has_permission(self, request, view):
        # Ensure the user is authenticated
        return request.user and request.user.is_authenticated


class FarmListCreateView(generics.ListCreateAPIView):
    """
    List all farms or create a new farm.
    """
    queryset = Farm.objects.all()
    serializer_class = FarmSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffPermission]

    def perform_create(self, serializer):
        # Automatically set the logged-in user as creatorId
        serializer.save(creatorId=self.request.user)



class FarmDetailView(APIView):
    """
    API view to retrieve details of a specific farm.
    """

    def get(self, request):
        company_id = request.query_params.get('company')
        farm_id = request.query_params.get('farm')
        app_name = request.query_params.get('app_name')  # Ensure `app_name` is provided in the request

        if not company_id or not farm_id or not app_name:
            raise PermissionDenied("The 'company', 'farm', and 'app_name' query parameters are required.")

        try:
            farm = Farm.objects.get(id=farm_id, company_id=company_id)
        except Farm.DoesNotExist:
            raise NotFound("Farm not found.")

        # Check if the requesting user has permission to access the farm
        if not has_permission(user=request.user, company=farm.company, app_name=app_name, model_name="Farm", action="view"):
            raise PermissionDenied("You do not have permission to view this farm.")

        # Pass companyID and other relevant data as part of the serializer context
        serializer = FarmSerializer(farm, context={'companyID': company_id})
        return Response(serializer.data)



class FarmPutViews(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific farm entry.
    """
    queryset = Farm.objects.all()
    serializer_class = FarmSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffPermission]


#StaffMember views
class StaffMemberListCreateView(generics.ListCreateAPIView):
    """
    List all staff members or assign a new staff member.
    Ensures the `has_permission` function is always called for each action.
    """
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer
    permission_classes = [IsAuthenticatedAndHasPermissionOrSelf]

    def validate_permissions(self, company_id, model_name, action, app_name="bsf"):
        """
        Validate permissions for the current user on the given company, app_name, and action.
        """
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        # Run the has_permission function
        if not has_permission(
            user=self.request.user,
            company=company,
            app_name=app_name,
            model_name=model_name,
            action=action
        ):
            raise PermissionDenied(f"You do not have permission to {action} this resource.")
        return company

    def get_queryset(self):
        """
        If the user is accessing their own records, filter by user.
        Otherwise, filter by company or farm based on query parameters.
        """
        user = self.request.user
        company_id = self.request.query_params.get("company")
        farm_id = self.request.query_params.get("farm")

        # Check if accessing self records
        if self.request.query_params.get("self", "false").lower() == "true":
            return StaffMember.objects.filter(user=user)

        # Ensure company_id is provided
        if not company_id:
            raise PermissionDenied("'company' query parameter is required.")

        # Validate permissions
        company = self.validate_permissions(company_id, model_name="StaffMember", action="view")

        # Filter queryset
        queryset = StaffMember.objects.filter(company=company)
        if farm_id:
            queryset = queryset.filter(farm_id=farm_id)

        return queryset

    def perform_create(self, serializer):
        """
        Validate permissions and create a new staff member.
        Automatically set the `created_by` field to the requesting user.
        """
        company_id = self.request.data.get("company")
        if not company_id:
            raise PermissionDenied("'company' is required in the request data.")

        # Validate permissions
        self.validate_permissions(company_id, model_name="StaffMember", action="add")

        # Save the instance
        serializer.save(created_by=self.request.user)

class AddStaffMemberView(generics.CreateAPIView):
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer
    permission_classes = [IsAuthenticatedAndHasPermissionOrSelf]

    def perform_create(self, serializer):
        user = self.request.user
        data = self.request.data
        company_id = data.get('company_id')
        user_id = data.get('user_id')
        farm_id = data.get('farm_id')

        # Validate company existence and permissions
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        if not has_permission(user, company, "StaffMember", "add"):
            raise PermissionDenied("You do not have permission to add staff members for this company.")

        # Validate user existence
        user_exists, user_instance = check_user_exists(user_id)
        if not user_exists:
            raise ValidationError("The specified user does not exist.")

        # Validate farm existence
        try:
            farm = Farm.objects.get(id=farm_id)
        except Farm.DoesNotExist:
            raise NotFound("The specified farm does not exist.")

        # Ensure the farm belongs to the company
        if farm.company.id != company.id:
            raise ValidationError("The farm does not belong to the specified company.")

        # Use the user's email if no work_email is provided
        work_email = data.get('work_email', user_instance.email)

        # Automatically set the added_by and approved_by fields to the authenticated user
        serializer.save(added_by=user, approved_by=user, work_email=work_email, company=company, user=user_instance, farm=farm)

    def get_object(self):
        """
        Ensure the filtered queryset logic is applied when retrieving a specific object.
        """
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=self.kwargs.get("pk"))
        self.check_object_permissions(self.request, obj)
        return obj
    
class StaffMemberDetailView(APIView):
    """
    API view to retrieve, update, or delete staff members.
    Always runs the has_permission function to validate user authority.
    """
    permission_classes = [IsAuthenticatedAndHasPermissionOrSelf]

    def validate_permissions(self, company_id, model_name, action, app_name="bsf"):
        """
        Validate permissions for the current user on the given company, app_name, and action.
        """
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        # Run the has_permission function
        if not has_permission(
            user=self.request.user,
            company=company,
            app_name=app_name,
            model_name=model_name,
            action=action
        ):
            raise PermissionDenied(f"You do not have permission to {action} this resource.")
        return company

    def get(self, request):
        """
        Retrieve staff members with active status for a company and farm.
        """
        company_id = request.query_params.get('company')
        farm_id = request.query_params.get('farm')
        user_id = request.query_params.get('user')

        # Validate required parameters
        if not company_id or not farm_id:
            raise PermissionDenied("The 'company' and 'farm' query parameters are required.")

        # Validate permissions
        company = self.validate_permissions(company_id, model_name="StaffMember", action="view")

        # Validate farm existence
        try:
            farm = Farm.objects.get(id=farm_id, company=company)
        except Farm.DoesNotExist:
            raise NotFound("The specified farm does not exist or does not belong to the company.")

        # Filter staff members with active status
        filters = {'company': company, 'farm': farm, 'status': 'active'}
        if user_id:
            filters['user_id'] = user_id

        staff_members = StaffMember.objects.filter(**filters)

        if not staff_members.exists():
            raise NotFound("No active staff members found for the specified criteria.")

        serializer = StaffMemberSerializer(staff_members, many=True)
        return Response(serializer.data)

    def put(self, request, pk=None):
        """
        Update a specific staff member.
        """
        company_id = request.data.get('company')
        if not company_id:
            raise PermissionDenied("'company' parameter is required.")

        # Validate permissions
        company = self.validate_permissions(company_id, model_name="StaffMember", action="edit")

        try:
            staff_member = StaffMember.objects.get(pk=pk, company=company)
        except StaffMember.DoesNotExist:
            raise NotFound("The specified staff member does not exist.")

        serializer = StaffMemberSerializer(staff_member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request):
        """
        Delete a specific user (status='active') for a given company and farm.
        """
        company_id = request.query_params.get('company')
        farm_id = request.query_params.get('farm')
        user_id = request.query_params.get('user')

        # Validate required parameters
        if not company_id or not farm_id or not user_id:
            raise PermissionDenied("The 'company', 'farm', and 'user' query parameters are required.")

        # Validate permissions
        company = self.validate_permissions(company_id, model_name="StaffMember", action="delete")

        # Validate farm existence
        try:
            farm = Farm.objects.get(id=farm_id, company=company)
        except Farm.DoesNotExist:
            raise NotFound("The specified farm does not exist or does not belong to the company.")

        # Attempt to retrieve the specific staff member
        try:
            staff_member = StaffMember.objects.get(
                user_id=user_id, company=company, farm=farm, status='active'
            )
        except StaffMember.DoesNotExist:
            raise NotFound("No active staff member found for the specified user, company, and farm.")

        # Delete the staff member
        staff_member.delete()
        return Response({"detail": "Active staff member deleted successfully."}, status=204)

# Net views
class NetListCreateView(generics.ListCreateAPIView):
    """
    View to list all Nets or create a new Net for a company and farm.
    """
    serializer_class = NetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filters Nets by company, farm, and optionally by id.
        """
        company_id = self.request.query_params.get('company')
        farm_id = self.request.query_params.get('farm')
        net_id = self.request.query_params.get('id')  # Optional Net ID
        queryset = Net.objects.all()

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if farm_id:
            queryset = queryset.filter(farm_id=farm_id)
        if net_id:
            queryset = queryset.filter(id=net_id)

        # Check partial access for view action
        result = has_permission(
            user=self.request.user,
            company=queryset.first().company if queryset.exists() else None,
            app_name="bsf",
            model_name="Net",
            action="view",
            requested_documents=queryset
        )

        # Handle permissions and filtering
        if result is True:
            return queryset
        if isinstance(result, list):
            ids = [doc.id for doc in result]
            return queryset.filter(id__in=ids)
        return queryset.none()

    def perform_create(self, serializer):
        """
        Validates and creates a new Net.
        """
        company = serializer.validated_data['company']
        farm = serializer.validated_data['farm']
        user = self.request.user

        # Validate user permissions
        if not has_permission(user, company, app_name="bsf", model_name="Net", action="add"):
            raise PermissionDenied("You do not have permission to add a Net for this company.")

        serializer.save()


class NetDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View to retrieve, update, or delete a specific Net.
    """
    serializer_class = NetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filters Nets by company, farm, and optionally by id.
        """
        company_id = self.request.query_params.get('company')
        farm_id = self.request.query_params.get('farm')
        net_id = self.request.query_params.get('id')  # Optional Net ID
        queryset = Net.objects.all()

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if farm_id:
            queryset = queryset.filter(farm_id=farm_id)
        if net_id:
            queryset = queryset.filter(id=net_id)

        return queryset

    def perform_update(self, serializer):
        """
        Validates and updates a Net.
        """
        company = serializer.validated_data.get('company', serializer.instance.company)
        farm = serializer.validated_data.get('farm', serializer.instance.farm)
        user = self.request.user

        # Validate user permissions
        if not has_permission(user, company, app_name="bsf", model_name="Net", action="edit"):
            raise PermissionDenied("You do not have permission to edit this Net.")

        serializer.save()

    def perform_destroy(self, instance):
        """
        Validates and deletes a Net and returns a success message.
        """
        company = instance.company
        user = self.request.user

        # Validate user permissions
        if not has_permission(user, company, app_name="bsf", model_name="Net", action="delete"):
            raise PermissionDenied("You do not have permission to delete this Net.")

        instance.delete()

    def delete(self, request, *args, **kwargs):
        """
        Overrides the DELETE method to include a success note.
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"detail": f"Net '{instance.name}' was successfully deleted."},
            status=status.HTTP_200_OK,
        )


class BatchListCreateView(generics.ListCreateAPIView):
    """
    View to list all batches or create a new batch.
    """
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        company_id = self.request.query_params.get("company")
        farm_id = self.request.query_params.get("farm")
        queryset = Batch.objects.all()

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if farm_id:
            queryset = queryset.filter(farm_id=farm_id)

        return queryset

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        farm = serializer.validated_data["farm"]
        user = self.request.user

        if not has_permission(user, company, app_name="bsf", model_name="Batch", action="add"):
            raise PermissionDenied("You do not have permission to create a batch for this company.")

        serializer.save()



class BatchDetailView(RetrieveUpdateDestroyAPIView):
    """
    View to retrieve, update, or delete a batch with associated data.
    """
    serializer_class = BatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Batch.objects.all()

    def get_object(self):
        """
        Override to include permission validation.
        """
        obj = super().get_object()

        # Check if the user has permission to view the batch
        has_permission(
            user=self.request.user,
            company=obj.company,
            app_name="bsf",
            model_name="Batch",
            action="view"
        )

        return obj


class DurationSettingsListCreateView(generics.ListCreateAPIView):
    """
    View to list all duration settings or create a new one.
    Incorporates `has_permission` validation.
    """
    
    queryset = DurationSettings.objects.all()
    serializer_class = DurationSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    

    def get_queryset(self):
        """
        Optionally filters by company and farm.
        """
        company_id = self.request.query_params.get("company")
        farm_id = self.request.query_params.get("farm")

        if not company_id:
            raise NotFound("The 'company' query parameter is required.")

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        # Check permissions
        has_permission(
            user=self.request.user,
            company=company,
            app_name="bsf",
            model_name="DurationSettings",
            action="view"
        )

        queryset = DurationSettings.objects.filter(company=company)
        if farm_id:
            queryset = queryset.filter(farm=farm_id)

        return queryset

    def perform_create(self, serializer):
        company_id = serializer.validated_data.get("company").id
        farm_id = serializer.validated_data.get("farm").id
        user = self.request.user

        

        # Validate if the farm exists and belongs to the company
        try:
            farm = Farm.objects.get(id=farm_id, company=company_id)
        except Farm.DoesNotExist:
            raise ValidationError({"farm": f"Farm with ID {farm_id} does not exist for Company {company_id}."})

        # Check if the user has permission
        if not has_permission(
            user=user,
            company=farm.company,
            app_name="bsf",
            model_name="DurationSettings",
            action="add",
        ):
            raise PermissionDenied("You do not have permission to add Duration Settings.")

        # Save the validated data
        serializer.save()


class DurationSettingsDetailView(APIView):
    """
    View to retrieve or update DurationSettings for a specific farm and company.
    Returns default DurationSettings (id=1) if no settings exist for the farm.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        company_id = request.query_params.get("company")
        farm_id = request.query_params.get("farm")

        if not company_id:
            raise NotFound("The 'company' query parameter is required.")

        # Validate the company exists
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        # Attempt to retrieve the specified farm's settings
        if farm_id:
            settings = DurationSettings.objects.filter(company=company, farm_id=farm_id).first()
        else:
            settings = DurationSettings.objects.filter(company=company, farm=None).first()

        # Fallback to default settings with ID=1 if no settings exist
        if not settings:
            settings = DurationSettings.objects.filter(id=1).first()

        # Serialize the result
        if not settings:
            raise NotFound("No default DurationSettings (id=1) found in the system.")

        serializer = DurationSettingsSerializer(settings)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        company_id = request.data.get("company")
        farm_id = request.data.get("farm")

        if not company_id:
            raise NotFound("The 'company' parameter is required.")

        # Validate the company exists
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        # Validate permissions for editing
        has_permission(
            user=request.user,
            company=company,
            app_name="bsf",
            model_name="DurationSettings",
            action="edit",
        )

        # Retrieve the DurationSettings to update
        settings = DurationSettings.objects.filter(company=company, farm_id=farm_id).first()
        if not settings:
            settings = DurationSettings.objects.filter(id=1).first()

        if not settings:
            raise NotFound("No default DurationSettings (id=1) found in the system.")

        # Perform update
        serializer = DurationSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)




class NetUseStatsListCreateView(generics.ListCreateAPIView):
    """
    View to list all NetUseStats or create a new entry.
    """
    serializer_class = NetUseStatsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company_id = self.request.query_params.get("company")
        farm_id = self.request.query_params.get("farm")

        if not company_id:
            raise PermissionDenied("'company' query parameter is required.")

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        # Check permissions for viewing
        has_permission(
            user=self.request.user,
            company=company,
            app_name="bsf",
            model_name="NetUseStats",
            action="view",
        )

        queryset = NetUseStats.objects.filter(company=company)

        if farm_id:
            queryset = queryset.filter(farm_id=farm_id)

        return queryset

    def perform_create(self, serializer):
        company_id = self.request.data.get("company")
        farm_id = self.request.data.get("farm")

        if not company_id:
            raise PermissionDenied("'company' parameter is required.")

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        # Validate permissions for adding
        has_permission(
            user=self.request.user,
            company=company,
            app_name="bsf",
            model_name="NetUseStats",
            action="add",
        )

        serializer.save(created_by=self.request.user)

class NetUseStatsDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View to retrieve, update, or delete a specific NetUseStats entry.
    Returns associated media data if <int:pk> (batchId) is provided.
    """
    queryset = NetUseStats.objects.all()
    serializer_class = NetUseStatsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Retrieve the NetUseStats object
        obj = super().get_object()

        # Validate permissions for viewing
        has_permission(
            user=self.request.user,
            company=obj.company,
            app_name="bsf",
            model_name="NetUseStats",
            action="view",
        )
        return obj

    def retrieve(self, request, *args, **kwargs):
        # Get the primary key from the URL
        batch_id = self.kwargs.get("pk")

        # Retrieve the NetUseStats object
        instance = self.get_object()

        # Retrieve associated media for the batch
        associated_media = Media.objects.filter(
            app_name="bsf",
            model_name="NetUseStats",
            model_id=batch_id,
            company=instance.company,
        )

        # Serialize the main NetUseStats object
        serializer = self.get_serializer(instance)

        # Serialize the associated media
        media_serializer = MediaSerializer(associated_media, many=True)

        # Return both the NetUseStats and associated media in the response
        return Response({
            "net_use_stats": serializer.data,
            "associated_media": media_serializer.data
        })

    def perform_update(self, serializer):
        obj = self.get_object()

        # Validate permissions for editing
        has_permission(
            user=self.request.user,
            company=obj.company,
            app_name="bsf",
            model_name="NetUseStats",
            action="edit",
        )
        serializer.save()

    def perform_destroy(self, instance):
        # Validate permissions for deleting
        has_permission(
            user=self.request.user,
            company=instance.company,
            app_name="bsf",
            model_name="NetUseStats",
            action="delete",
        )
        instance.delete()
