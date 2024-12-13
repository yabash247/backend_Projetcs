# views.py
from rest_framework import generics, permissions, status
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import Farm, StaffMember, Net, Batch, DurationSettings, NetUseStats, Pond, PondUseStats
from company.models import Company, Media  # Import the Company model
from company.serializers import MediaSerializer
from .serializers import FarmSerializer, StaffMemberSerializer, NetSerializer, BatchSerializer, DurationSettingsSerializer, NetUseStatsSerializer, PondSerializer, PondUseStatsSerializer
from rest_framework.permissions import BasePermission, IsAuthenticated
from company.utils import has_permission, check_user_exists, get_associated_media, handle_media_uploads
from django.shortcuts import get_object_or_404
from django.db import transaction
from copy import deepcopy
import logging


def validate_company_and_farm(request):
    """
    Validates that:
    1. Company and Farm are provided in the request.
    2. The Company exists.
    3. The Farm exists.
    4. The Farm belongs to the specified Company.

    Args:
        request: The incoming HTTP request containing 'company' and 'farm' parameters.

    Returns:
        dict: A dictionary containing the validated 'company' and 'farm' instances.

    Raises:
        Response: Returns an error response if any validation fails.
    """
    company_id = request.query_params.get("company") or request.data.get("company")
    farm_id = request.query_params.get("farm") or request.data.get("farm")

    if not company_id or not farm_id:
        return Response(
            {"detail": "'company' and 'farm' parameters are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Fetch and validate the company
    company = get_object_or_404(Company, id=company_id)

    # Fetch and validate the farm
    farm = get_object_or_404(Farm, id=farm_id)

    # Ensure the farm belongs to the specified company
    if farm.company_id != company.id:
        return Response(
            {"detail": f"Farm '{farm.name}' does not belong to Company '{company.name}'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    return {"company": company, "farm": farm}

def validate_company_farm_and_batch(request):
    """
    Validates that:
    1. Company, Farm, and Batch are provided in the request.
    2. The Company exists.
    3. The Farm exists and belongs to the specified Company.
    4. The Batch exists and belongs to the specified Farm.

    Args:
        request: The incoming HTTP request containing 'company', 'farm', and 'batch' parameters.

    Returns:
        dict: A dictionary containing the validated 'company', 'farm', and 'batch' instances.

    Raises:
        Response: Returns an error response if any validation fails.
    """
    company_id = request.query_params.get("company") or request.data.get("company")
    farm_id = request.query_params.get("farm") or request.data.get("farm")
    batch_id = request.query_params.get("batch") or request.data.get("batch")

    if not company_id or not farm_id or not batch_id:
        return Response(
            {"detail": "'company', 'farm', and 'batch' parameters are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Fetch and validate the company
    company = get_object_or_404(Company, id=company_id)

    # Fetch and validate the farm
    farm = get_object_or_404(Farm, id=farm_id)
    if farm.company_id != company.id:
        return Response(
            {"detail": f"Farm '{farm.name}' does not belong to Company '{company.name}'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Fetch and validate the batch
    batch = get_object_or_404(Batch, id=batch_id, farm=farm)

    return {"company": company, "farm": farm, "batch": batch}

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



class NetDetailView_status(ListAPIView):
    """
    View to list Nets, ensuring only those with "completed" status in NetUseStats
    or without any associated NetUseStats are included.
    """
    serializer_class = NetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Filters Nets by company and farm.
        Includes Nets not in NetUseStats and excludes those with "ongoing" status.
        """
        company_id = self.request.query_params.get('company')
        farm_id = self.request.query_params.get('farm')

        if not company_id or not farm_id:
            raise ValueError("Both 'company' and 'farm' query parameters are required.")

        queryset = Net.objects.filter(company_id=company_id, farm_id=farm_id)

        # Exclude Nets with "ongoing" status and include those not in NetUseStats
        ongoing_net_ids = NetUseStats.objects.filter(stats="ongoing").values_list('net_id', flat=True)
        queryset = queryset.exclude(id__in=ongoing_net_ids)

        return queryset


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


'''
Example JSON data for creating a new NetUseStats entry:
class NetUseStatsListCreateView(generics.ListCreateAPIView):{
    "company": 1,
    "farm": 2,
    "batch": 3,
    "net": 5,
    "lay_start": "2024-12-06",
    "stats": "ongoing",
    "media": [
        {"title": "Net Image 1", "file": "<file_1>"},
        {"title": "Net Image 2", "file": "<file_2>"}
    ]
}
'''

from rest_framework.decorators import action
from django.db.models import Q  # Add Q for advanced filtering

class NetUseStatsListCreateView(generics.ListCreateAPIView):
    """
    View to list all NetUseStats, create a new entry, and upload media files.
    """
    serializer_class = NetUseStatsSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Override create to handle both creating NetUseStats and uploading media.
        """
        # Handle NetUseStats creation
        response = super().create(request, *args, **kwargs)

        # If creation is successful, handle media uploads
        if response.status_code == status.HTTP_201_CREATED:
            netusestats_id = response.data["id"]  # Capture the ID of the created NetUseStats
            media_response = self._handle_media_uploads(request, netusestats_id)
            if media_response.status_code != status.HTTP_201_CREATED:
                return media_response

        return response

    @transaction.atomic
    def perform_create(self, serializer):
        """
        Creates a new NetUseStats entry.
        """
        company, _ = self._get_company_and_validate_permissions("add", for_create=True)
        # Save and capture the created instance
        self.instance = serializer.save(created_by=self.request.user, company=company)

    def _handle_media_uploads(self, request, netusestats_id):
        """
        Handle media uploads after successful NetUseStats creation.
        """
        company_id = request.data.get("company")
        if not company_id:
            return Response({"detail": "'company' parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch and validate company
        company = get_object_or_404(Company, id=company_id)

        # Parse and organize media data
        media_files = []
        for key, value in request.data.items():
            if key.startswith("media_title_"):
                index = key.split("_")[-1]
                media_files.append({"index": index, "title": value, "file": None})
            elif key.startswith("media_file_"):
                index = key.split("_")[-1]
                media_entry = next((item for item in media_files if item["index"] == index), None)
                if media_entry:
                    media_entry["file"] = request.FILES.get(key)

        # Validate and save each media file
        for media_entry in media_files:
            if not media_entry["file"]:
                return Response(
                    {"detail": f"File missing for media entry with index {media_entry['index']}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                Media.objects.create(
                    title=media_entry["title"],
                    file=media_entry["file"],
                    company=company,
                    app_name="bsf",
                    model_name="NetUseStats",
                    model_id=netusestats_id,  # Use the ID of the newly created NetUseStats
                    status="active",
                    comments="",
                    uploaded_by=request.user,
                )
            except Exception as e:
                return Response({"detail": f"Error saving file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"detail": "Media files uploaded successfully."}, status=status.HTTP_201_CREATED)


    def _get_company_and_validate_permissions(self, action, for_create=False):
        """
        Retrieves the company based on the request and validates permissions.
        """
        company_id = self.request.query_params.get("company") if not for_create else self.request.data.get("company")
        farm_id = self.request.query_params.get("farm") if not for_create else self.request.data.get("farm")

        if not company_id:
            raise PermissionDenied("'company' parameter is required.")

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise NotFound("The specified company does not exist.")

        has_permission(
            user=self.request.user,
            company=company,
            app_name="bsf",
            model_name="NetUseStats",
            action=action,
        )

        return company, farm_id


class NetUseStatsDetailViewss(generics.RetrieveUpdateAPIView):
    """
    View to retrieve and update NetUseStats data, including handling media uploads via PATCH.
    """
    serializer_class = NetUseStatsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Returns queryset for the given batchId, farm, and company with validation checks.
        """
        batch_id = self.kwargs.get("pk")  # batchId from URL
        company_id = self.request.query_params.get("company")
        farm_id = self.request.query_params.get("farm")

        if not company_id or not farm_id:
            raise ValidationError("Both 'company' and 'farm' query parameters are required.")

        company = get_object_or_404(Company, id=company_id)
        farm = get_object_or_404(Farm, id=farm_id, company=company)

        # Check user permission
        has_permission(
            user=self.request.user,
            company=company,
            app_name="bsf",
            model_name="NetUseStats",
            action="view",
        )

        return NetUseStats.objects.filter(company=company, farm=farm, created_by=self.request.user.id)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        """
        Handle PATCH requests to update NetUseStats and associated media files.
        """
        netusestats_id = self.kwargs.get("pk")

        company_id = request.data.get("company")
        if not company_id:
            return Response({"detail": "'company' parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch and validate company
        company = get_object_or_404(Company, id=company_id)

        # Check user permission
        has_permission(
            user=self.request.user,
            company=company,
            app_name="bsf",
            model_name="NetUseStats",
            action="edit",
        )

        # Update the main NetUseStats instance
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Handle media uploads
        media_response = self._handle_media_uploads(request, netusestats_id)
        if media_response.status_code != status.HTTP_201_CREATED:
            return media_response

        return Response({"detail": "NetUseStats and media updated successfully."}, status=status.HTTP_200_OK)

    def _handle_media_uploads(self, request, netusestats_id):
        """
        Handle media uploads for NetUseStats updates.
        """
        company_id = request.data.get("company")
        if not company_id:
            return Response({"detail": "'company' parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch and validate company
        company = get_object_or_404(Company, id=company_id)

        # Parse media data
        media_files = self._parse_media_data(request)

        # Validate and save each media file
        for media_entry in media_files:
            if not media_entry["file"]:
                return Response(
                    {"detail": f"File missing for media entry with index {media_entry['index']}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                Media.objects.create(
                    title=media_entry["title"],
                    file=media_entry["file"],
                    company=company,
                    app_name="bsf",
                    model_name="NetUseStats",
                    model_id=netusestats_id,
                    status="active",
                    comments=media_entry["comments"],
                    uploaded_by=request.user,
                )
            except Exception as e:
                return Response({"detail": f"Error saving file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"detail": "Media files uploaded successfully."}, status=status.HTTP_201_CREATED)

    def _parse_media_data(self, request):
        """
        Parse media-related keys from the request and group them by index.
        """
        media_files = []
        for key, value in request.data.items():
            if key.startswith("media_title_"):
                index = key.split("_")[-1]
                media_files.append({"index": index, "title": value, "file": None, "comments": None})
            elif key.startswith("media_file_"):
                index = key.split("_")[-1]
                media_entry = next((item for item in media_files if item["index"] == index), None)
                if media_entry:
                    media_entry["file"] = request.FILES.get(key)
            elif key.startswith("media_comments_"):
                index = key.split("_")[-1]
                media_entry = next((item for item in media_files if item["index"] == index), None)
                if media_entry:
                    media_entry["comments"] = value
        return media_files

class NetUseStatsDetailView(generics.RetrieveUpdateAPIView):
    """
    View to retrieve and update NetUseStats data, including handling media uploads via PATCH.
    """
    serializer_class = NetUseStatsSerializer
    permission_classes = [IsAuthenticated]

    def validate_request_data(self, data, required_fields):
        """
        Helper method to validate required fields in the request data.
        """
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            raise ValidationError(
                f"The following fields are required: {', '.join(missing_fields)}"
            )

    def get_queryset(self):
        """
        Returns queryset for the given batchId, farm, and company with validation checks.
        """
        company_id = self.request.data.get("company")
        farm_id = self.request.data.get("farm")

        # Validate required query parameters
        if not company_id or not farm_id:
            raise ValidationError("Both 'company' and 'farm' query parameters are required.")

        company = get_object_or_404(Company, id=company_id)
        farm = get_object_or_404(Farm, id=farm_id, company=company)

        # Check user permission
        has_permission(
            user=self.request.user,
            company=company,
            app_name="bsf",
            model_name="NetUseStats",
            action="view",
        )

        return NetUseStats.objects.filter(company=company, farm=farm, created_by=self.request.user.id)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        """
        Handle PATCH requests to update NetUseStats and associated media files.
        """
        netusestats_id = self.kwargs.get("pk")
        data = request.data

        # Validate required fields
        self.validate_request_data(data, ["company", "farm", "batch"])

        company_id = data.get("company")
        farm_id = data.get("farm")
        batch_id = data.get("batch")

        # Fetch and validate models
        company = get_object_or_404(Company, id=company_id)
        farm = get_object_or_404(Farm, id=farm_id)
        batch = get_object_or_404(Batch, id=batch_id)

        # Validate farm-company relationship
        if farm.company_id != company.id:
            return Response(
                {"detail": f"Farm with ID {farm_id} does not belong to the company with ID {company_id}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check user permission
        has_permission(
            user=self.request.user,
            company=company,
            app_name="bsf",
            model_name="NetUseStats",
            action="edit",
        )

        # Update the main NetUseStats instance
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Handle media uploads
        try:
            media_response = handle_media_uploads(
                request=request,
                data_id=netusestats_id,
                model_name="NetUseStats",
                app_name="bsf"
            )
            if media_response.status_code != status.HTTP_201_CREATED:
                return media_response
        except Exception as e:
            return Response({"detail": f"Error during media upload: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"detail": "NetUseStats and media updated successfully."}, status=status.HTTP_200_OK)

from django.core.exceptions import ObjectDoesNotExist

class NetUseStatsRetrieveAllView(APIView):
    """
    API view to retrieve NetUseStats for a specific company, farm, and batch.
    Optionally retrieves data for a specified ID using the query parameter (?id=<id>).
    Includes associated media for each NetUseStats entry.
    """
    permission_classes = [IsAuthenticated]

    def get_object_or_404(self, model, **kwargs):
        """
        Helper method to get an object or raise a 404 response.
        """
        try:
            return model.objects.get(**kwargs)
        except model.DoesNotExist:
            raise ObjectDoesNotExist

    def validate_query_params(self, params, required_fields):
        """
        Helper method to validate required query parameters.
        """
        for field in required_fields:
            if not params.get(field):
                return Response(
                    {"detail": f"'{field}' query parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return None

    def get(self, request, *args, **kwargs):
        # Required query parameters
        query_params = request.query_params
        validation_error = self.validate_query_params(query_params, ["company", "farm", "batch"])
        if validation_error:
            return validation_error

        company_id = query_params.get("company")
        farm_id = query_params.get("farm")
        batch_id = query_params.get("batch")
        net_use_stats_id = query_params.get("id")

        # Fetch and validate models
        try:
            company = self.get_object_or_404(Company, id=company_id)
            farm = self.get_object_or_404(Farm, id=farm_id)
            batch = self.get_object_or_404(Batch, id=batch_id)
        except ObjectDoesNotExist as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

        # Check if the farm belongs to the company
        if farm.company_id != company.id:
            return Response(
                {"detail": f"Farm with ID {farm_id} does not belong to the company with ID {company_id}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Query NetUseStats
        queryset = NetUseStats.objects.filter(company=company, farm=farm, batch=batch)
        if not queryset.exists():
            return Response(
                {"detail": f"No NetUseStats entries found for the specified parameters."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Retrieve a single entry if `id` is provided
        if net_use_stats_id:
            try:
                net_use_stat = queryset.get(id=net_use_stats_id)
            except NetUseStats.DoesNotExist:
                return Response(
                    {"detail": f"NetUseStats with ID {net_use_stats_id} does not exist in the specified filters."},
                    status=status.HTTP_404_NOT_FOUND
                )

            return self.build_response(net_use_stat, company)

        # Retrieve all matching entries
        return self.build_response(queryset, company)

    def build_responses(self, data, company):
        """
        Helper method to build the response with associated media.
        """
        if isinstance(data, NetUseStats):
            data = [data]

        result = []
        for net_use_stat in data:
            serialized_data = NetUseStatsSerializer(net_use_stat).data
            associated_media = get_associated_media(
                data_id=net_use_stat.id,
                model_name="NetUseStats",
                app_name="bsf",
                company=company,
            )
            media_serializer = MediaSerializer(associated_media, many=True)
            serialized_data["associated_media"] = media_serializer.data
            result.append(serialized_data)

        return Response(result, status=status.HTTP_200_OK)

    def build_response(self, data, company):
        """
        Helper method to build the response with associated media and net data.
        """
        if isinstance(data, NetUseStats):
            data = [data]

        result = []
        for net_use_stat in data:
            # Serialize NetUseStats
            serialized_data = NetUseStatsSerializer(net_use_stat).data
            
            # Fetch associated media
            associated_media = get_associated_media(
                data_id=net_use_stat.id,
                model_name="NetUseStats",
                app_name="bsf",
                company=company,
            )
            media_serializer = MediaSerializer(associated_media, many=True)
            serialized_data["associated_media"] = media_serializer.data

            # Fetch and include associated Net data
            try:
                associated_net = Net.objects.get(id=net_use_stat.net_id)
                net_serializer = NetSerializer(associated_net)
                serialized_data["associated_net"] = net_serializer.data
            except Net.DoesNotExist:
                serialized_data["associated_net"] = None

            # Add to the response list
            result.append(serialized_data)

        return Response(result, status=status.HTTP_200_OK)



def save_media_files(media_data, company, app_name, model_name, model_id, user):
    """
    Saves media files associated with a specific model instance.

    Args:
        media_data (list): A list of dictionaries containing media details (title, file).
        company (Company): The company associated with the media.
        app_name (str): The app name where the requesting model resides.
        model_name (str): The name of the requesting model.
        model_id (int): The ID of the associated model instance.
        user (User): The user making the request.

    Returns:
        list: A list of created Media instances.
    """
    created_media = []

    for item in media_data:
        title = item.get("title")
        file = item.get("file")

        if not title or not file:
            raise ValidationError("Each media entry must include 'title' and 'file'.")

        media_instance = Media.objects.create(
            title=title,
            file=file,
            company=company,
            app_name=app_name,
            model_name=model_name,
            model_id=model_id,
            status="active",
            uploaded_by=user,
        )
        created_media.append(media_instance)

    return created_media

# NetUseStats views change retuend net value from id to name.
def build_response(self, data, company):
    """
    Helper method to build the response with associated media and replace `id` with `name`.
    """
    if isinstance(data, NetUseStats):
        data = [data]

    result = []
    for net_use_stat in data:
        serialized_data = NetUseStatsSerializer(net_use_stat).data

        # Replace `id` with `name`
        serialized_data['name'] = net_use_stat.name  # Ensure the model has a `name` attribute
        if 'id' in serialized_data:
            del serialized_data['id']

        # Fetch associated media
        associated_media = get_associated_media(
            data_id=net_use_stat.id,
            model_name="NetUseStats",
            app_name="bsf",
            company=company,
        )
        media_serializer = MediaSerializer(associated_media, many=True)
        serialized_data["associated_media"] = media_serializer.data
        result.append(serialized_data)

    return Response(result, status=status.HTTP_200_OK)


def post(self, request, *args, **kwargs):
    """
    Handle POST requests to upload media files with flat structure.
    """
    company_id = request.data.get("company")
    if not company_id:
        return Response({"detail": "'company' parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Fetch and validate company
    company = get_object_or_404(Company, id=company_id)

    # Parse and organize media data
    media_files = []
    for key, value in request.data.items():
        if key.startswith("media_title_"):
            index = key.split("_")[-1]
            media_files.append({"index": index, "title": value, "file": None})
        elif key.startswith("media_file_"):
            index = key.split("_")[-1]
            media_entry = next((item for item in media_files if item["index"] == index), None)
            if media_entry:
                media_entry["file"] = request.FILES.get(key)

    # Validate and save each media file
    for media_entry in media_files:
        if not media_entry["file"]:
            return Response(
                {"detail": f"File missing for media entry with index {media_entry['index']}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            Media.objects.create(
                title=media_entry["title"],
                file=media_entry["file"],
                company=company,
                app_name="bsf",
                model_name="NetUseStats",
                model_id=request.data.get("net"),  # Assuming `net` represents the NetUseStats ID
                status="active",
                comments="",  # Add comments handling if required
                uploaded_by=request.user,
            )
        except Exception as e:
            return Response({"detail": f"Error saving file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({"detail": "Media files uploaded successfully."}, status=status.HTTP_201_CREATED)


class PondView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def get(self, request, *args, **kwargs):
        """
        Handles:
        - Viewing all ponds or a specific pond by ID.
        - Returning only available ponds or checking if a specific pond is available.
        """
        company_id = request.query_params.get("company")
        farm_id = request.query_params.get("farm")
        pond_id = kwargs.get("id")
        is_available_query = request.query_params.get("available")  # Request to check if the pond is available for use (no ongoing stats)

        if not company_id or not farm_id:
            return Response({"detail": "'company' and 'farm' parameters are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch and validate the company and farm
        company = get_object_or_404(Company, id=company_id)
        farm = get_object_or_404(Farm, id=farm_id, company=company)

        # Check permissions
        has_permission(request.user, company, "bsf", "Pond", "view")

        if pond_id:
            # Retrieve a specific pond by ID
            pond = get_object_or_404(Pond, id=pond_id, farm=farm, company=company)

            if is_available_query == "true":
                pond = get_object_or_404(Pond, id=pond_id, farm=farm, company=company, status="Active")
                # Check if the specific pond is available
                ongoing_status = PondUseStats.objects.filter(farm=farm, pond=pond, status="Ongoing").exists()
                if not ongoing_status:
                    media = get_associated_media(pond.id, "Ponds", "bsf", company)
                    pond_data = {
                        "pond": PondSerializer(pond).data,
                        "associated_media": MediaSerializer(media, many=True).data
                    }
                    return Response({"available": True, "pond_data": pond_data}, status=status.HTTP_200_OK)
                return Response({"available": False, "pond_data": None}, status=status.HTTP_200_OK)

            # If `available` is not requested, return the specific pond details
            media = get_associated_media(pond.id, "Ponds", "bsf", company)
            pond_data = {
                "pond": PondSerializer(pond).data,
                "associated_media": MediaSerializer(media, many=True).data
            }
            return Response(pond_data, status=status.HTTP_200_OK)

        if is_available_query == "true":
            # Fetch only available ponds
            active_ponds = Pond.objects.filter(farm=farm, company=company, status="Active")
            available_ponds = [
                pond for pond in active_ponds
                if not PondUseStats.objects.filter(farm=farm, pond=pond, status="Ongoing").exists()
            ]
            results = []
            for pond in available_ponds:
                media = get_associated_media(pond.id, "Ponds", "bsf", company)
                results.append({
                    "pond": PondSerializer(pond).data,
                    "associated_media": MediaSerializer(media, many=True).data
                })
            return Response(results, status=status.HTTP_200_OK)

        # Default behavior: Fetch all ponds
        ponds = Pond.objects.filter(farm=farm)
        results = []
        for pond in ponds:
            media = get_associated_media(pond.id, "Ponds", "bsf", company)
            results.append({
                "pond": PondSerializer(pond).data,
                "associated_media": MediaSerializer(media, many=True).data
            })
        return Response(results, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """
        Create a new pond.
        """
        company_id = request.data.get("company")
        farm_id = request.data.get("farm")

        if not company_id or not farm_id:
            return Response({"detail": "'company' and 'farm' parameters are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch and validate the company and farm
        company = get_object_or_404(Company, id=company_id)
        farm = get_object_or_404(Farm, id=farm_id, company=company)

        # Check permissions
        has_permission(request.user, company, "bsf", "Pond", "add")

        # Create a mutable copy of request.data
        data = deepcopy(request.data)
        data["farm"] = farm.id  # Associate with the farm
        data["created_by"] = request.user.id  # Set created_by to the logged-in user

        serializer = PondSerializer(data=data)

        if serializer.is_valid():
            pond = serializer.save()

            # Handle associated media uploads
            handle_media_uploads(request, pond.id, "Pond", "bsf")

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        """
        Edit an existing pond.
        """
        company_id = request.data.get("company")
        farm_id = request.data.get("farm")
        pond_id = kwargs.get("id")

        if not company_id or not farm_id or not pond_id:
            return Response({"detail": "'company', 'farm', and 'pond_id' parameters are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch and validate the company, farm, and pond
        company = get_object_or_404(Company, id=company_id)
        farm = get_object_or_404(Farm, id=farm_id, company=company)
        pond = get_object_or_404(Pond, id=pond_id, farm=farm)

        # Check permissions
        has_permission(request.user, company, "bsf", "Pond", "edit")

        # Create a mutable copy of request.data
        data = deepcopy(request.data)

        serializer = PondSerializer(pond, data=data, partial=True)
        if serializer.is_valid():
            updated_pond = serializer.save()

            # Handle associated media uploads
            handle_media_uploads(request, updated_pond.id, "Pond", "bsf")

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PondUseStatsView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated
    
    VALID_HARVEST_STAGES = {
            "Incubation": "Incubation",
            "Nursery": "Nursery",
            "Growout": "Growout",
            "PrePupa": "PrePupa",
            "Pupa": "Pupa"
        }

    def get(self, request, *args, **kwargs):
        """
        Retrieve PondUseStats for a specific batch, farm, and company, optionally filtered by harvest_stage.
        """
        validation_result = validate_company_farm_and_batch(request)
        if isinstance(validation_result, Response):
            return validation_result

        company = validation_result["company"]
        farm = validation_result["farm"]
        batch = validation_result["batch"]
        pondusestats_id = kwargs.get("id")
        ongoing = request.query_params.get("ongoing", "false").lower() == "true"
        harvest_stage = request.query_params.get("harvest_stage")

        # Check for invalid harvest_stage
        if harvest_stage and harvest_stage not in self.VALID_HARVEST_STAGES:
            return Response(
                {"detail": f"Invalid harvest_stage '{harvest_stage}'. Valid options are: {list(self.VALID_HARVEST_STAGES.keys())}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check permissions
        has_permission(request.user, company, "bsf", "PondUseStats", "view")

        if pondusestats_id:
            # Fetch a single PondUseStats by ID
            pondusestats = PondUseStats.objects.filter(
                id=pondusestats_id, farm=farm, batch=batch
            )
            if ongoing:
                pondusestats = pondusestats.filter(status="Ongoing")

            if harvest_stage:
                pondusestats = pondusestats.filter(harvest_stage=self.VALID_HARVEST_STAGES[harvest_stage])

            if not pondusestats.exists():
                return Response(
                    {"detail": "PondUseStats not found or does not match the provided filters."},
                    status=status.HTTP_404_NOT_FOUND
                )

            pondusestats = pondusestats.first()
            media = get_associated_media(pondusestats.id, "PondUseStats", "bsf", company)
            return Response({
                "pondusestats": PondUseStatsSerializer(pondusestats).data,
                "associated_media": MediaSerializer(media, many=True).data,
            }, status=status.HTTP_200_OK)

        # Fetch all PondUseStats for the batch
        pondusestats_query = PondUseStats.objects.filter(farm=farm, batch=batch)
        if ongoing:
            pondusestats_query = pondusestats_query.filter(status="Ongoing")

        if harvest_stage:
            pondusestats_query = pondusestats_query.filter(harvest_stage=self.VALID_HARVEST_STAGES[harvest_stage])

        results = [
            {
                "pondusestats": PondUseStatsSerializer(pondusestats).data,
                "associated_media": MediaSerializer(
                    get_associated_media(pondusestats.id, "PondUseStats", "bsf", company),
                    many=True
                ).data,
            }
            for pondusestats in pondusestats_query
        ]

        return Response(results, status=status.HTTP_200_OK)
    def post(self, request, *args, **kwargs):
        """
        Create a new PondUseStats.
        """
        validation_result = validate_company_farm_and_batch(request)
        if isinstance(validation_result, Response):
            return validation_result

        company = validation_result["company"]
        farm = validation_result["farm"]
        batch = validation_result["batch"]
        pond_id = request.data.get("pond")

        if not pond_id:
            return Response(
                {"detail": "'pond' parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        pond = get_object_or_404(Pond, id=pond_id, farm=farm)

        # Check permissions
        has_permission(request.user, company, "bsf", "PondUseStats", "add")

        if pond.status != "Completed":
            return Response(
                {"detail": "Pond status must be 'Completed' to create PondUseStats."},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()
        data.update({
            "pond": pond.id,
            "batch": batch.id,
            "created_by": request.user.id,
        })

        serializer = PondUseStatsSerializer(data=data)
        if serializer.is_valid():
            pondusestats = serializer.save()
            handle_media_uploads(request, pondusestats.id, "PondUseStats", "bsf")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        """
        Update an existing PondUseStats.
        """
        validation_result = validate_company_farm_and_batch(request)
        if isinstance(validation_result, Response):
            return validation_result

        company = validation_result["company"]
        farm = validation_result["farm"]
        batch = validation_result["batch"]
        pondusestats_id = kwargs.get("id")

        if not pondusestats_id:
            return Response(
                {"detail": "'pondusestats_id' parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        pondusestats = get_object_or_404(PondUseStats, id=pondusestats_id, farm=farm, batch=batch)

        # Check permissions
        has_permission(request.user, company, "bsf", "PondUseStats", "edit")

        data = request.data.copy()
        if "approver_id" in data and data["approver_id"] != str(request.user.id):
            return Response(
                {"detail": "Only the logged-in user can set approver_id."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = PondUseStatsSerializer(pondusestats, data=data, partial=True)
        if serializer.is_valid():
            updated_ponduse_stats = serializer.save()
            handle_media_uploads(request, updated_ponduse_stats.id, "PondUseStats", "bsf")
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



