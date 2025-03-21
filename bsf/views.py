# views.py
from rest_framework import generics, permissions, status
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import Farm, StaffMember, Net, Batch, DurationSettings, NetUseStats, Pond, PondUseStats as PondUseStatsModel, PondUseStats
from company.models import Company, Media, Task, ActivityOwner, Branch # Import the Company model

from company.serializers import MediaSerializer
from .serializers import FarmSerializer, StaffMemberSerializer, NetSerializer, BatchSerializer, DurationSettingsSerializer, NetUseStatsSerializer, PondSerializer, PondUseStatsSerializer
from rest_framework.permissions import BasePermission, IsAuthenticated
from company.utils import has_permission, check_user_exists, get_associated_media, handle_media_uploads, extract_common_data
from django.shortcuts import get_object_or_404
from django.db import transaction
from copy import deepcopy
from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Q  # Add Q for advanced filtering
from django.core.exceptions import ObjectDoesNotExist
import logging
import datetime
import re
import requests
import os
import json
from decouple import config
from twilio.twiml.messaging_response import MessagingResponse
from django.core.cache import cache
import urllib.parse
from decimal import Decimal
from users.models import UserProfile  # Add this line to import UserProfile


logger = logging.getLogger(__name__)

#whatsapp messaging needed imports
from twilio.twiml.messaging_response import MessagingResponse
import requests

#Step 7: Deploy Your Webhook (Optional)
    #VPS (Ubuntu, Nginx, Gunicorn)
    #This allows Twilio to access your webhook permanently.


from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os

def _handle_media_files(self, request, common_data, net_use_stat, lay_index):
    """
    Handles media file uploads associated with a specific layStart.
    """
    media_index = 0
    while f"media_title_{lay_index}_{media_index}" in request.data:
        file = request.FILES.get(f"media_file_{lay_index}_{media_index}")
        if not file:
            raise ValidationError("Media file is required.")

        try:
            # Save the file to a persistent location
            saved_path = default_storage.save(
                os.path.join("uploads", file.name), ContentFile(file.read())
            )
            absolute_path = default_storage.path(saved_path)

            company = Company.objects.get(id=common_data["company"])
            branch = Branch.objects.get(company=company, branch_id=common_data["farm"])

            Media.objects.create(
                title=request.data[f"media_title_{lay_index}_{media_index}"],
                file=saved_path,  # Store the saved path
                comments=request.data.get(f"media_comments_{lay_index}_{media_index}", ""),
                company=company,
                app_name=common_data["appName"],
                model_name=common_data["modelName"],
                model_id=net_use_stat.id,
                uploaded_by=request.user,
                status="active",
                branch=branch,
                created_date=now(),
            )
            logging.info(f"Media file {media_index} uploaded for layStart {lay_index}")
            media_index += 1
        except Exception as e:
            logging.error(f"Error saving media file: {str(e)}")
            raise


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


def validate_company_branch_and_batch(request):
    """
    Validates that:
    1. Company, Branch, and Batch are provided in the request.
    2. The Company exists.
    3. The Branch exists and belongs to the specified Company.
    4. The Batch exists and belongs to the specified Branch.

    Args:
        request: The incoming HTTP request containing 'company', 'Branch', and 'batch' parameters.

    Returns:
        dict: A dictionary containing the validated 'company', 'Branch', and 'batch' instances.

    Raises:
        Response: Returns an error response if any validation fails.
    """
    company_id = request.query_params.get("company") or request.data.get("company")
    branch_id = request.query_params.get("branch") or request.data.get("branch")
    batch_id = request.query_params.get("batch") or request.data.get("batch")
    status = request.query_params.get("status") or request.data.get("status")
    pondusestats = request.query_params.get("id") or request.data.get("id")
    #print(company_id, branch_id, batch_id)

    if not company_id or not branch_id or not batch_id:
        return Response(
            {"detail": "'company', 'branch', and 'batch' parameters are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Fetch and validate the company
    company = get_object_or_404(Company, id=company_id)
    #print(company)

    # Fetch and validate the branch
    branch = get_object_or_404(Branch, id=branch_id, company=company)

    if branch.company_id != company.id:
        return Response(
            {"detail": f"Branch '{branch.name}' does not belong to Company '{company.name}'."},
            status=status.HTTP_400_BAD_REQUEST
        )
    farm = get_object_or_404(Farm, company=company, id=branch.branch_id, status="active")
    #print(farm)

    # Fetch and validate the batch
    batch = get_object_or_404(Batch, batch_name=batch_id, farm=farm, company=company)
    #print(batch)

    print(pondusestats)
    # Fetch and validate the pondusestats
    pondusestats = get_object_or_404(PondUseStatsModel, id=pondusestats, batch=batch, company=company, farm=farm)
    print(pondusestats)

    return {"company": company, "branch": branch, "farm":farm, "batch": batch, "status":status, "pondusestats":pondusestats}


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


# Branch views
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
        branch_id = request.query_params.get('branch')
        user_id = request.query_params.get('user')


        if not company_id:
            userStaffData = StaffMember.objects.filter(user=request.user, status="active").first()
            if not userStaffData : 
                raise PermissionDenied("'company' query parameter is required.")
            return Response(StaffMemberSerializer(userStaffData, many=False).data)
        
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
        Filters Nets by company and branch.
        Includes Nets not in NetUseStats and excludes those with "ongoing" status.
        """
        company_id = self.request.query_params.get('company')
        branch_id = self.request.query_params.get('branch')

        if not company_id or not branch_id:
            raise ValueError("Both 'company' and 'farm' query parameters are required.")
        
        # Fetch Nets for the specified company and branch
        company = Company.objects.filter(id=company_id, status='active').first()
        if not company:
            raise NotFound("The specified company does not exist.")
        branch = Branch.objects.filter(id=branch_id, company=company, status='active').first()
        if not branch:
            raise NotFound("The specified branch does not exist or does not belong to the company.")

        queryset = Net.objects.filter(company=company, branch=branch)

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

        # Save the batch
        batch = serializer.save()
        branch = Branch.objects.filter(company=company, branch_id=farm.id).first()
        if not branch:
            raise ValidationError(f"No branch found for farm '{farm.name}' in this company.")
        # Fetch the staff member in charge of laying
        laying_staff = ActivityOwner.objects.filter(
            company=company,
            branch=branch,  # Assuming branch and farm are linked correctly
            activity="Laying_Start",
            appName= "bsf",
            modelName= "NetInUse",
            status="active"
        ).first()

        # Determine assigned user for the task
        if laying_staff:
            print(f"Laying staff found: {laying_staff.owner}")
            assigned_to = laying_staff.owner  # Use the staff owner if available
            assistant = laying_staff.assistant  # Use the staff owner if available
        else:
            company_owner = Company.objects.filter(id=company.id).first()
            if not company_owner or not company_owner.creator:
                raise ValidationError("No laying staff or company creator found for task assignment.")
            assigned_to = company_owner.creator  # Fallback to company creator
            assistant = company_owner.creator  # Fallback to company creator

        # Create a Task for Net Use Start Info
        task_title = f"Add Net Details Used For Batch: {batch.batch_name}'s,  Eggs Laying"
        task_description = f"""
        Task Details:
        - Batch: {batch.batch_name}
        - Required: [
            - Lay Start: ?
            - Stage: Laying_Start
            - Stats: Ongoing
            - Media: True for points allocation
            ]
        """
        task_due_date = now() + timedelta(days=1)  # Due tomorrow
        # Ensure branch is resolved correctly
        branch = Branch.objects.filter(company=company, branch_id=farm.id).first()
        if not branch:
            raise ValidationError(f"No branch found for farm '{farm.name}' in this company.")
        
        Task.objects.create(
            company=company,
            branch=branch,  # Ensure this is a valid Branch instance
            title=task_title,
            description=task_description,
            due_date=task_due_date,
            assigned_to=assigned_to,
            assistant=assistant,
            appName = "bsf",
            modelName = "NetInUse",
            activity = "Laying_Start",
            status="active"
        )

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
    View to list all NetUseStats, create a new entry, and upload media files.
    """
    serializer_class = NetUseStatsSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        try:

            # Check if the request is from WhatsApp
            if "From" in request.data and "Body" in request.data:
                print("Processing  data sent from whatsapp.....")
                return self.process_whatsapp_submission(request)
            

            # Extract and validate common data
            print("Extracting and validating common data...")
            common_data = self._extract_and_validate_common_data(request)
            if isinstance(common_data, Response):  # Handle validation errors
                return common_data
            
            self.company = Company.objects.get(id=common_data["company"], status="active")
            self.branch = Branch.objects.get(id=common_data["branch"], company=self.company, status="active")
            #print(f"Branch: {self.branch}")
            self.farm = Farm.objects.get(id=self.branch.branch_id, company=self.company, status="active")
            #print(f"farm: {self.farm}")
            self.batch = Batch.objects.get(batch_name=common_data["batch"], company=self.company, farm=self.farm)

            # Initialize completeDetails
            self.completeDetails = ""

            # Process layStarts and associated media
            print("Processing layStarts and media...")
            self._process_lay_starts_and_media(request, common_data)

            # Update task and create the next task
            print("Updating task and creating next task...")
            self._update_task_and_create_next_step(request, common_data)

            print("Activity processed successfully.")
            return Response(
                {"detail": f"{common_data['activity']} activity processed successfully."},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            # Log and return the error message
            logging.error(f"Error during creation: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _extract_and_validate_common_data(self, request):
        """
        Extracts and validates common data from the request.
        """
        required_fields = [
            "taskId",
            "taskTitle",
            #"createdDate",
            "appName",
            "modelName",
            "activity",
            "batch",
            "branch",
            "company",
        ]
        data = {field: request.data.get(field) for field in required_fields}

        # Ensure all required fields are provided
        missing_fields = [field for field, value in data.items() if not value]
        if missing_fields:
            logging.warning(f"Missing fields: {missing_fields}")
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return data

    def _process_lay_starts_and_media(self, request, common_data):
        """
        Processes activity and associated media files from the request.
        """
        try:

            lay_index = 0
            while f"net_{lay_index}" in request.data:



                if common_data["activity"] == "Laying_Start":
                        
                        net = Net.objects.get(
                            id=request.data[f"net_{lay_index}"], company=self.company, farm=self.farm
                        )

                        # Check if net.id, company, and farm with status="ongoing" exist in NetUseStats
                        print(f"Checking if NetUseStats exists for Net {net}...")
                        if NetUseStats.objects.filter(net=net, company=self.company, farm=self.farm, stats="ongoing").exists():
                            print(f"Net {net} is already in use with ongoing status. by batch {self.batch.batch_name}")
                            raise ValidationError(f"Net {net} is already in use with ongoing status. by batch {self.batch.batch_name}")
                        
                        
                        net_use_stat = NetUseStats.objects.create(
                            batch=self.batch,
                            farm=self.farm,
                            company=self.company,
                            net=net,
                            lay_start=request.data[f"startDate_{lay_index}"],
                            created_by=request.user,
                        )
                        self.model_id = net_use_stat.id
                        self._handle_media_files(request, common_data, net_use_stat, lay_index)
                        self.completeDetails += f"[ - appName = {common_data['appName']},  - modelName = {common_data['modelName']}, - modelId = {net_use_stat.id},  - activity = {common_data['activity']}, - filledOut = {'lay_start'}]"
                        
                
                elif common_data["activity"] == "Laying_End":

                    print("Processing Laying_End activity...")

                    net_use_id = request.data.get("modelID"); 
                    print(f"NetUseID is: {net_use_id}")

                    if not net_use_id:
                        print("NetUseID is required.")
                        raise ValidationError("The 'netUseID' parameter is required.")
                    
                    net_use_stat = NetUseStats.objects.filter(company=self.company, id=net_use_id, batch=self.batch, farm=self.farm, stats="ongoing").first(); 
                    print(f"NetUseStat is: {net_use_stat}")
                    
                    if not net_use_stat:
                        raise ValidationError("No ongoing NetUseStats found for the specified ID.")
                    
                    netInstance = net_use_stat.net; 
                    print(f"Net Id is: {netInstance.id}")

                    net = Net.objects.get(company=self.company, id=netInstance.id, branch=self.branch, farm=self.farm, status="active"); 
                    print(f"Net: {net.id}")
                    
                    self.harvested_eggs = request.data.get( f"harvestWeight_{lay_index}"); print(f"Harvested Eggs: {self.harvested_eggs}")
                    expect_harvest = net.expect_harvest; print(f"Expected Harvest: {expect_harvest}")
                    
                    if self.harvested_eggs is None:
                        self.harvested_eggs = 0
                    if expect_harvest is None:
                        expect_harvest = 0

                    percentScore = (float(self.harvested_eggs) / float(expect_harvest)) * 100
                    if percentScore >= 90:
                        laying_ratting = "outstanding"
                    elif percentScore >= 75:
                        laying_ratting = "exceeds_expectation"
                    elif percentScore >= 50:
                        laying_ratting = "satisfactory"
                    elif percentScore >= 25:
                        laying_ratting = "unsatisfactory"
                    else:
                        laying_ratting = "poor"

                    print(f"percentScore: {percentScore}")
                    print(f"Laying Ratting: {laying_ratting}")

                    # Update the NetUseStats object
                    net_use_stat.lay_end = request.data.get( f"endDate_{lay_index}");  print(f"Lay End: {net_use_stat.lay_end}")
                    net_use_stat.harvest_weight = self.harvested_eggs
                    net_use_stat.stats = "completed"
                    net_use_stat.created_by = request.user
                    net_use_stat.laying_ratting = laying_ratting
                    net_use_stat.save()
                    self._handle_media_files(request, common_data, net_use_stat, 0)
                    self.completeDetails += f"[ - appName = {common_data['appName']},  - modelName = {common_data['modelName']}, - modelId = {net_use_stat.id},  - activity = {common_data['activity']}, - filledOut = {'lay_end, harvest_weight'}]"
                
                lay_index += 1


        except Exception as e:
            logging.error(f"Error processing lay starts and media: {str(e)}")
            raise

    def _handle_media_files(self, request, common_data, net_use_stat, lay_index):
        """
        Handles media file uploads associated with a specific layStart.
        """
        media_index = 0
        while f"media_title_{lay_index}_{media_index}" in request.data:
            file = request.FILES.get(f"media_file_{lay_index}_{media_index}")
            media_title = request.FILES.get(f"media_title_{lay_index}_{media_index}")

            if not media_title and not file:
                print(f"Skipping media upload for layer {lay_index}, media {media_index}")
                return  # Skip if media is missing

            #if not file:
                #raise ValidationError("Media file is required.")
            

            try:
                # Save the file to a persistent location
                # Define the dynamic upload path
                def save_media_file(file, common_data, net_use_stat, lay_index, media_index):
                    """
                    Saves a media file to a persistent location and returns the saved path.
                    """
                    upload_path = os.path.join(
                        common_data["appName"],
                        common_data["modelName"],
                        str(net_use_stat.id),
                        f"media_{lay_index}_{media_index}_{file.name}"
                    )
                    saved_path = default_storage.save(upload_path, ContentFile(file.read()))
                    return saved_path

                # Usage in the _handle_media_files method
                saved_path = save_media_file(file, common_data, net_use_stat, lay_index, media_index)

                Media.objects.create(
                    title=request.data[f"media_title_{lay_index}_{media_index}"],
                    file=saved_path,  # Store the saved path
                    comments=request.data.get(f"media_comments_{lay_index}_{media_index}", ""),
                    company=self.company,
                    app_name=common_data["appName"],
                    model_name=common_data["modelName"],
                    model_id=net_use_stat.id,
                    uploaded_by=request.user,
                    status="active",
                    branch=self.branch,
                )
                print(f"Media file {media_index} uploaded for layStart or layEnd {lay_index}")
                media_index += 1
            except Exception as e:
                logging.error(f"Error saving media file: {str(e)}")
                raise

    def _update_task_and_create_next_step(self, request, common_data):
        """
        Updates the current task's status and creates a new task for the next step.
        """

        """
        Creates the next task in the workflow dynamically based on the activity.
        """
        print("Creating the next task in the workflow...")
        # Update batch information
        batch = Batch.objects.filter(
            company=self.company,
            farm=self.farm,
            batch_name=common_data["batch"],
        ).first()
        #print(f"Batch: {batch}")

        # Fetch duration settings dynamically for the company's branch
        duration = DurationSettings.objects.filter(company=self.company, farm=self.farm).first(); print(f"Duration: {duration}")

        # Determine the next task based on the activity
        
        if common_data["activity"] == "Laying_Start":
            # Calculate the due date for the next task
            laying_duration = duration.laying_duration if duration else 3
            next_task_due_date = now() + timedelta(days=laying_duration)
            next_activity = "Laying_End"
            title=f"Harvest and provide Eggies harvest data for batch {common_data['batch']}",
            description=f"""
                Task Details:
                - Batch: {common_data['batch']}
                - model_id : {self.model_id}
                - Required:
                  - Lay end: ?
                  - Stage: Laying_End
                  - Harvest weight: ?
                  - Stats: completed
                  - Media: True for points allocation
                """,
        
            #this would be incorrect if laying for particular batch ever gets edited or updated again
            if batch:
                #print("Updating batch information...")
                batch = Batch.objects.get(id=batch.id)

                # Get the start date string from request data
                start_date_str = request.data.get(f"startDate_0")
                if not start_date_str:
                    raise ValidationError("Start date is required.")
                
                # Update fields
                batch.laying_start_date  = start_date_str
                batch.cretated_by  = request.user

                # Save the updated batch object
                print("Saving batch...")
                batch.save()
                print("Batch information successfully updated.")
        
        elif common_data["activity"] == "Laying_End":
            # Calculate the due date for the next task
            net = NetUseStats.objects.get(id=request.data.get("modelID"), company=self.company, farm=self.farm); print(f"Net: {net.net}")
            next_task_due_date = now()
            next_activity = "Incubation"
            title=f"Need to Incubate the {self.harvested_eggs}grams of eggs harvested from Net{net.net.name}: for batch: {common_data['batch']}",
            description=f"""
                Task Details:
                - Batch: {common_data['batch']}
                - from Net: {net.net.name}
                - Required:
                    - Set Date
                    - Start Weight
                    - Pond
                    - Stats: ongoing
                    - Media: True for points allocation
                """,
            '''
            #this would be incorrect if laying for particular batch ever gets edited or updated again

            
            if batch:
                #print("Updating batch information...")
                batch = Batch.objects.get(id=batch.id)

                # Get the start date string from request data
                end_date_str = request.data.get(f"lay_end")
                if not end_date_str:
                    raise ValidationError("End date is required.")
                
                # Update fields
                batch.laying_end_date  = end_date_str
                batch.laying_harvest_quantity  = request.data.get("harvestedEggs")
                batch.laying_status  = "completed"
                batch.cretated_by  = request.user

                # Save the updated batch object
                print("Saving batch...")
                batch.save()
                print("Batch information successfully updated.")

            # '''
            
        else:
            # Handle other activities if needed
            next_activity = "Unknown"
            next_task_due_date = now()
            title = f"Unknown task for activity {common_data['activity']}"
            description = f"Task for {common_data['activity']} is not defined."
        
        if next_activity == "Unknown":
            raise ValidationError("Unknown activity. Task not created.")
        
        # Fetch the activity owner for the next task
        activity_info = ActivityOwner.objects.filter(
            company=self.company,
            branch=self.branch,
            activity=next_activity,
            status="active",
        ).first()

        if not activity_info:
            #assign task to manager if only one manager exisit in the company's branch else
            #assign task to the director in the company's branch
            managers = StaffMember.objects.filter(company=self.company, branch=self.branch, position="manager", status="active")
            if managers.count() == 1:
                self.assigned_to = managers.first().user
            else:
                directors = StaffMember.objects.filter(company=self.company, branch=self.branch, position="director", status="active")
                if directors.exists():
                    self.assigned_to = directors.first().user
                else:
                    raise ValidationError("No suitable manager or director found for task assignment.")
        if activity_info:
            print(f"Activity Owner: {activity_info.owner}")
            self.assigned_to = activity_info.owner if activity_info.owner else (activity_info.assistant if activity_info.assistant else activity_info.owner.lead)
        else:
            self.assigned_to = None

        # Create the next task in the workflow
        Task.objects.create(
            company=self.company,
            branch=self.branch,
            title=title,
            description=description,
            due_date=next_task_due_date,
            assigned_to=self.assigned_to if self.assigned_to else None,
            assistant=activity_info.assistant if activity_info else None,
            appName=activity_info.appName if activity_info else None,
            modelName=activity_info.modelName if activity_info else None,
            activity = activity_info.activity if activity_info else None,
            status="active", 
        )

        try:
            task = Task.objects.filter(
                id=common_data["taskId"],
                title=common_data["taskTitle"],
                company=common_data["company"],
                appName=common_data["appName"],
                modelName=common_data["modelName"],
                activity=common_data["activity"],
            ).first()
            #print(self.completeDetails)
            if task:
                task.status = "pending"
                task.completeDetails = self.completeDetails
                task.completed_by = request.user
                task.completed_date = now()
                task.save()

                # Create the next task in the workflow
                #self._create_next_task(request, common_data)

            '''
            
                # Update batch information -  has to be done at the end of all batch activities
                batch = Batch.objects.filter(
                    company=self.company,
                    farm=self.farm,
                    batch_name=common_data["batch"],
                ).first()
                if batch:
                    #print("Updating batch information...")
                    batch = Batch.objects.get(id=batch.id)

                    # Get the start date string from request data
                    start_date_str = request.data.get(f"startDate_0")
                    if not start_date_str:
                        raise ValidationError("Start date is required.")
                    
                    # Update fields
                    batch.laying_start_date  = start_date_str
                    batch.cretated_by  = request.user

                    # Save the updated batch object
                    print("Saving batch...")
                    batch.save()
                    print("Batch information successfully updated.")
            '''
        except Exception as e:
            logging.error(f"Error updating task or batch: {str(e)}")
            raise

    def _create_next_task(self, request, common_data):
        """
        Creates the next task in the workflow.
        """
        

        duration = DurationSettings.objects.filter(
            company=self.company,
            farm=self.farm,
        ).first()

        laying_duration = duration.laying_duration if duration else 3
        new_task_due_date = now() + timedelta(days=laying_duration)

        

        activity_info = ActivityOwner.objects.filter(
            company=self.company,
            branch=self.branch,
            activity="Laying_End",
            status="active",
        ).first()

        batch = Batch.objects.filter(
                    company=self.company,
                    farm=self.farm,
                    batch_name=common_data["batch"],
                ).first()

        Task.objects.create(
            company=self.company,
            branch=self.branch,
            title=f"Harvest and provide Eggies harvest data for batch {common_data['batch']}",
            description="""
            Task Details:
            - Batch: {batch_name}
            - Required:
              - Lay end: ?
              - Harvest weight: ?
              - Stats: pending
              - Media: True for points allocation
            """.format(batch_name=common_data["batch"]),
            due_date=new_task_due_date,
            assigned_to=activity_info.owner if activity_info else None,
            assistant=activity_info.assistant if activity_info else None,
            appName="bsf",
            modelName="NetInUse",
            status="active",
            activity = activity_info.activity if activity_info else None,
        )
        logging.info("Next task created successfully.")


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

    def process_whatsapp_submission(self, request):
        """
        Processes WhatsApp task completion messages and formats them like TaskList.tsx submissions.
        """
        sender = request.data.get("From")  # Staff's WhatsApp number
        message = request.data.get("Body").strip()  # WhatsApp message body
        media_url = request.data.get("MediaUrl0")  # First media file (if any)

        response = MessagingResponse()
        task_id = None

        if message.lower().startswith("start task"):
            task_id = message.split()[-1]

            # Find the corresponding task in the company Task model
            task = Task.objects.filter(id=task_id, assigned_to__phone_number=sender, status="active").first()
            if not task:
                response.message("❌ Task not found or already completed.")
                return Response(str(response), content_type="text/xml")

            # Mark task as "in_progress"
            task.status = "in_progress"
            task.save()
            response.message(f"✅ Task {task_id} started. Please enter the completion date (YYYY-MM-DD).")
            return Response(str(response), content_type="text/xml")

        elif message.lower().startswith("date:"):
            task_id = message.split()[1]

            # Retrieve task in progress
            task = Task.objects.filter(id=task_id, assigned_to__phone_number=sender, status="in_progress").first()
            if not task:
                response.message("❌ Task not found or not in progress.")
                return Response(str(response), content_type="text/xml")

            task.completed_date = message.split()[2]  # Extract the entered date
            response.message("📸 Upload a photo as proof or type SKIP if not needed.")
            return Response(str(response), content_type="text/xml")

        elif media_url:
            # Retrieve the ongoing task
            task_id = request.data.get("task_id")
            task = Task.objects.filter(id=task_id, assigned_to__phone_number=sender, status="in_progress").first()
            if not task:
                response.message("❌ Task not found.")
                return Response(str(response), content_type="text/xml")

            # Format the request data to match `TaskList.tsx` submission
            formatted_data = {
                "taskId": task.id,
                "taskTitle": task.title,
                "appName": task.appName,
                "modelName": task.modelName,
                "activity": task.activity,
                "batch": task.company.id,  # Assuming batch is linked to the company
                "branch": task.branch.id if task.branch else None,
                "company": task.company.id,
                "completed_date": task.completed_date,
                "media_file": media_url,  # Media file URL from WhatsApp
            }

            # Call the `bsf/net-use-stats/` API
            api_response = requests.post(
                "https://yourserver.com/api/bsf/net-use-stats/",
                data=formatted_data
            )

            if api_response.status_code == 201:
                task.status = "completed"
                task.completeDetails = "Completed via WhatsApp"
                task.save()

                response.message("✅ Task successfully completed!")
            else:
                response.message(f"❌ Error processing task. {api_response.text}")

            return Response(str(response), content_type="text/xml")

        response.message("❌ Invalid command. Type 'Start Task <TaskID>' to begin.")
        return Response(str(response), content_type="text/xml")



    

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
        print("Retrieving NetUseStats...")
        # Required query parameters
        query_params = request.query_params
        validation_error = self.validate_query_params(query_params, ["company", "branch", "batch"])
        if validation_error:
            return validation_error

        company_id = query_params.get("company")
        branch_id = query_params.get("branch")
        batch_name = query_params.get("batch")
        #print(f"Company: {company_id}, Branch: {branch_id}, Batch: {batch_name}")
        net_use_stats_id = query_params.get("modelID")
        #print(f"NetUseStats ID: {net_use_stats_id}")

        # Fetch and validate models
        try:
            company = self.get_object_or_404(Company, id=company_id)
            branch = self.get_object_or_404(Branch, id=branch_id, company=company)
            farm = self.get_object_or_404(Farm, id=branch.branch_id, company=company)
            batch = self.get_object_or_404(Batch, batch_name=batch_name, company=company, farm=farm)
            #print(f"Batch: {batch}")
        except ObjectDoesNotExist as e:
            return Response({"detail": str(e)}, status=status.HTTP_404_NOT_FOUND)

        # Check if the farm belongs to the company
        if farm.company_id != company.id:
            return Response(
                {"detail": f"Farm with ID {branch_id} does not belong to the company with ID {company_id}."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
        # Check if the batch exists
        if not batch:
            return Response(
                {"detail": f"Batch '{batch_name}' does not exist for the specified company and farm."},
                status=status.HTTP_404_NOT_FOUND
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
        
        # Filter by status if provided
        status_param = query_params.get("stats")
        if status_param:
            valid_status_choices = [choice[0] for choice in NetUseStats.STATUS_CHOICES]
            if status_param not in valid_status_choices:
                return Response(
                    {"detail": f"Invalid status '{status_param}'. Valid options are: {valid_status_choices}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            queryset = queryset.filter(stats=status_param)

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



class PondView(APIView):
    permission_classes = [IsAuthenticated]  # Ensure the user is authenticated

    def get(self, request, *args, **kwargs):
        """
        Handles:
        - Viewing all ponds or a specific pond by ID.
        - Returning only available ponds or checking if a specific pond is available.
        """
        self.company_id = request.query_params.get("company")
        self.branch_id = request.query_params.get("branch")
        self.pond_id = kwargs.get("id")
        self.is_available_query = request.query_params.get("available")  # Request to check if the pond is available for use (no ongoing stats)

        print(f"Company: {self.company_id}, Branch: {self.branch_id}, Pond: self.{self.pond_id}, Available: {self.is_available_query}")

        if not self.company_id or not self.branch_id:
            return Response({"detail": "'company' and 'Branch' parameters are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch and validate the company and farm
        company = get_object_or_404(Company, id=self.company_id, status="active")
        branch = get_object_or_404(Branch, id=self.branch_id, company=company, status="active")
        farm = get_object_or_404(Farm, id=branch.branch_id, company=company, status="active")
        print(f"Company: {company}, Branch: {branch}, Farm: {farm}")
        

        # Check permissions
        has_permission(request.user, company, "bsf", "Pond", "view")

        if self.pond_id:
            # Retrieve a specific pond by ID
            pond = get_object_or_404(Pond, id=self.pond_id, farm=farm, company=company)

            if self.is_available_query == "true":
                pond = get_object_or_404(Pond, id=self.pond_id, farm=farm, company=company, status="Active"); print ( f"pond: {pond}")
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

        if self.is_available_query == "true":
            print("Checking for available ponds...")
            # Fetch only available ponds
            active_ponds = Pond.objects.filter(farm=farm, company=company, status="Active"); #print(f"Active Ponds: {active_ponds}")

            available_ponds = [
                pond for pond in active_ponds
                if not PondUseStatsModel.objects.filter(farm=farm, pond=pond, status="Ongoing").exists()
            ]
            #print(f"Available Ponds: {available_ponds}")
            results = []

            for pond in available_ponds:
                media = get_associated_media(pond.id, "Ponds", "bsf", company); print(f"Available Ponds: {media}")
                results.append({
                    "pond": PondSerializer(pond).data,
                    "associated_media": MediaSerializer(media, many=True).data
                })
                #print(f"Available Ponds: {results}")
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
        print("**********PondUseStatsView ***********")
        """
        Retrieve PondUseStats for a specific batch, farm, and company, optionally filtered by harvest_stage.
        """
        validation_result = validate_company_branch_and_batch(request)
        if isinstance(validation_result, Response):
            return validation_result

        #print("Validation result: ", validation_result)
        company = validation_result["company"]
        farm = validation_result["farm"]
        branch = validation_result["branch"]
        batch = validation_result["batch"]
        pondusestats = validation_result["pondusestats"]
        stats = validation_result["status"]
        #pondusestats_id = kwargs.get("id")
        #print(f"Company: {company}, Farm: {farm}, Branch: {branch}, Batch: {batch}, Status: {status}, PondUseStats: {pondusestats}")
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

        pondusestats_id = request.query_params.get("id") or request.data.get("id")
        if pondusestats_id:
            # Fetch a single PondUseStats by ID
            pondusestats = PondUseStatsModel.objects.filter(
                id=pondusestats_id, farm=farm, batch=batch, company=company
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
        pondusestats_query = PondUseStatsModel.objects.filter(branch=branch, batch=batch)
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

class PondUseStats(APIView):

    serializer_class = PondUseStatsSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        try:
            print("********start of create****************")

            # Define the fields to extract
            required_fields = [
                "branch",
                "company",
                "batch",
            ]
            # Extract common data
            self.common_data = extract_common_data(request, required_fields); #print(f"Common Data: {self.common_data}")
            if isinstance(self.common_data, Response):  # Handle validation errors
                return self.common_data   
            
            # Create instances 
            self.company = Company.objects.get(id=self.common_data["company"], status="active")
            self.branch = Branch.objects.get(id=self.common_data["branch"], company=self.company, status="active"); #print(f"Branch: {self.branch}")
            self.farm = Farm.objects.get(id=self.branch.branch_id, company=self.company, status="active")    
            self.batch = Batch.objects.get(company=self.company, farm=self.farm, batch_name=self.common_data["batch"]); #print(f"Batch: {self.batch}")

            # Initialize completeDetails
            self.completeDetails = ""

            # Extract activity type from the request
            self.activity = request.data.get("activity")
            #print(f"Activity: {self.activity}")
            if not self.activity:
                raise ValidationError("'activity' parameter is required.")
            
            # Process based on activity type
            if self.activity not in ["Incubation", "Nursery", "Growout", "PrePuppa", "Puppa"]:
                return Response(
                    {"detail": f"Unsupported activity type: {self.activity}"},
                    status=status.HTTP_400_BAD_REQUEST,)
            
            # Extract stage type from the request
            self.endOrStart = request.data.get("stage")
            #print(f"End or Start: {self.endOrStart}")
            if not self.endOrStart:
                raise ValidationError("'End or Start' parameter is needs to be defined and is required.")
            
            return self._handle_activity(request)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    def _handle_activity(self, request):
        #print("********start of handle_activity****************")
        with transaction.atomic():
            if self.endOrStart == "Start":
                return self._start_activity(request)
            elif self.endOrStart == "End":
                return self._end_activity(request)
        
        # If no valid stage, return a Response
        return Response({"error": "Invalid 'stage' parameter."}, status=status.HTTP_400_BAD_REQUEST)

    def _start_activity(self, request):
        print("********Handle the start of an activity.********")
        layer_index = 0

        while f"pond_{layer_index}" in request.data:
            pond_id = request.data.get(f"pond_{layer_index}")
            start_date = request.data.get(f"startDate_{layer_index}")
            start_weight = request.data.get(f"startWeight_{layer_index}")

            if not pond_id or not start_date or not start_weight:
                logging.warning(f"Skipping missing pond entry at index {layer_index}")
                layer_index += 1
                continue  # Skip this iteration

            pond = get_object_or_404(Pond, id=pond_id, farm=self.farm, company=self.company, status="Active")

            if not pond:
                raise ValidationError(f"Pond '{pond_id}' does not exist or is not active.")

            exisitngPondUseStats = PondUseStatsModel.objects.filter(pond=pond, status="Ongoing").first()

            if exisitngPondUseStats is not None:
                if exisitngPondUseStats.batch == self.batch and exisitngPondUseStats.company == self.company and exisitngPondUseStats.farm == self.farm:
                    if self.activity in ["Incubation", "Nursery"] and self.endOrStart == "Start":
                        exisitngPondUseStats.harvest_stage = self.activity
                        exisitngPondUseStats.start_weight += start_weight
                        exisitngPondUseStats.comments += f"\n{request.user} updated data by adding {start_weight} from net for batch {self.batch.batch_name} on {now()}"
                        exisitngPondUseStats.save()
                    raise ValidationError(f"Pond '{pond.pond_name}' already has an ongoing activity for the same batch, company, and farm.")

                raise ValidationError(f"Pond '{pond.pond_name}' already has an ongoing activity.")

            # Create new PondUseStats
            self.pond_use_stats = PondUseStatsModel.objects.create(
                pond=pond,
                farm=self.farm,
                company=self.company,
                batch=self.batch,
                start_date=start_date,
                start_weight=start_weight,
                harvest_stage=self.activity,
                status="Ongoing",
                created_by=request.user,
            )

            self._handle_layer_media(request, self.pond_use_stats.id, layer_index)
            self.completeDetails += f"[ - appName=bsf, modelName=PondUseStats, modelId={self.pond_use_stats.id}, activity={self.activity}, filledOut=start_date, start_weight]"

            # Call task completion and next task creation
            self._complete_task_and_create_next(request)
            layer_index += 1

        return Response(
            {"detail": f"{self.activity} activity started successfully for batch: {self.batch.batch_name}."},
            status=status.HTTP_201_CREATED,
        )


    def _end_activity(self, request):
        """Handle the end of an activity with multiple layers and media."""
        print("""********Handle the end of an activity.********""")

        pond_use_stats_id = request.data.get("modelID"); print(f"pond_use_stats_id: {pond_use_stats_id}")
        if not pond_use_stats_id:
            raise ValidationError("'modelID' parameter is required for ending an activity.")
        
        layer_index = 0
        while f"id_{layer_index}" in request.data:
            #pond_use_stats_id = request.data.get(f"id_{layer_index}"); print(f"pond_use_stats_id: {pond_use_stats_id}")
            end_date = request.data.get(f"endDate_{layer_index}")
            harvest_weight = request.data.get(f"harvestWeight_{layer_index}")

            if not end_date or not harvest_weight:
                raise ValidationError(
                    f" 'endDate_{layer_index}', and 'harvestWeight_{layer_index}' are required for ending an activity."
                )

            self.dataToSave = get_object_or_404(
                PondUseStatsModel, 
                id=pond_use_stats_id, 
                company=self.company, 
                farm=self.farm, 
                batch=self.batch, 
                status="Ongoing"
            )
            print(f"Pond Use Stats: {self.dataToSave}")

            try:
                with transaction.atomic():

                    # Convert end_date to a datetime.date object
                    if isinstance(end_date, str):
                        try:
                            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
                        except ValueError:
                            raise ValidationError(f"Invalid format for end_date: {end_date}. Expected 'YYYY-MM-DD'.")

                    if not isinstance(end_date, datetime.date):
                        raise ValueError(f"Invalid harvest_date: {end_date}. Expected a date object.")
                    self.dataToSave.harvest_date = end_date

                    try:
                        harvest_weight = Decimal(harvest_weight)
                    except (ValueError, TypeError):
                        raise ValueError(f"Invalid harvest_weight: {harvest_weight}. Expected a float or Decimal.")
                    self.dataToSave.harvest_weight = harvest_weight

                    self.dataToSave.status = "Completed"
                    self.dataToSave.save()
            
            except Exception as e:
                print(f"Transaction error: {str(e)}")

            print(f"Layer Index: {layer_index}")
            self._handle_layer_media(request, self.dataToSave.id, layer_index)
            self.completeDetails += f"[ - appName=bsf, modelName=PondUseStats, modelId={self.dataToSave.id}, activity={self.activity}, filledOut=end_date, harvest_weight]"
            layer_index += 1

        self._complete_task_and_create_next(request)

        return Response(
            {"detail": f"{self.activity} activity ended successfully for {layer_index} layers."},
            status=status.HTTP_200_OK,)

    def _handle_layer_media(self, request, pond_use_stats_id, layer_index):
        """Handle media uploads for a specific layer."""
        media_index = 0
        while f"media_title_{layer_index}_{media_index}" in request.data:
            media_title = request.data.get(f"media_title_{layer_index}_{media_index}")
            media_file = request.FILES.get(f"media_file_{layer_index}_{media_index}")
            media_comments = request.data.get(f"media_comments_{layer_index}_{media_index}", "")
            
            if not media_title and not media_file:
                print(f"Skipping media upload for layer {layer_index}, media {media_index}")
                return  # Skip if media is missing

            Media.objects.create(
                title=media_title,
                file=media_file,
                comments=media_comments,
                company=self.company,
                branch=self.branch,
                app_name="bsf",
                model_name="PondUseStats",
                model_id=pond_use_stats_id,
                uploaded_by=request.user,
                status="active",
            )

            media_index += 1

    def _complete_task_and_create_next(self, request):
        """Complete the current task and create the next task."""
        task_id = request.data.get("taskId")
        task_title = request.data.get("taskTitle")
        #print(f"Task ID: {task_id}, Task Title: {task_title}")
        if task_id and task_title:
            task = Task.objects.filter(
                id=task_id, title=task_title, company=self.company, activity=self.activity
            ).first()
            #print(f"Task: {task}")
            if task:
                task.status = "pending"
                task.completed_date = now()
                task.completeDetails = self.completeDetails
                task.completed_by = request.user
                task.save()
                print(f"Task: {task}")
        return self._create_next_task()
    
    
    def _create_next_task(self):
        """Create the next task in the workflow."""
        if not hasattr(self, 'pond_use_stats'):
            logging.warning("Skipping next task creation: pond_use_stats not found.")
            return Response(
                {"detail": "Cannot create the next task. Missing pond data."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activity_order = ["Incubation", "Nursery", "Growout", "PrePuppa", "Puppa"]
        current_activity = self.activity

        description = ""

        if self.endOrStart == "Start":
            next_stage = "End"
            next_activity = current_activity
            description = f"""
                Task Details:
                - Batch: {self.batch.batch_name}
                - model_id : {self.pond_use_stats.id}
                - Pond: {self.pond_use_stats.pond.pond_name}
                - Activity: {next_activity}
                - Stage: {next_stage}
                - Required:
                    - Harvest Date
                    - Harvest Weight
                    - Stats: completed
                    - Media: True for points allocation
                """
        elif self.endOrStart == "End":
            if not hasattr(self, 'dataToSave'):
                return Response(
                    {"detail": "Cannot create the next task. Missing pond or pond use stats."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            savedPond = self.dataToSave.pond
            try:
                next_activity = activity_order[activity_order.index(current_activity) + 1]
                next_stage = "Start"
                description = f"""
                Task Details:
                - Batch: {self.batch.batch_name}
                - Pond_use_stats: {self.dataToSave.id}
                - Pond: {savedPond.pond_name}
                - Activity: {next_activity}
                - Stage: {next_stage}
                - Required:
                    - Set Date
                    - Start Weight
                    - Pond
                    - Stats: ongoing
                    - Media: True for points allocation
                """
            except (ValueError, IndexError):
                return Response(
                    {"detail": "No next activity available. Workflow completed."},
                    status=status.HTTP_200_OK,
                )

        # Fetch duration settings
        duration_setting = DurationSettings.objects.filter(company=self.company, farm=self.farm).first()
        task_due_date = now() + timedelta(days=getattr(duration_setting, f"{next_activity.lower()}_duration", 3))

        # Fetch the activity owner for the next task
        activity_owner = ActivityOwner.objects.filter(
            company=self.company, branch=self.branch, activity=next_activity, status="active"
        ).first()

        # Create the next task in the workflow
        Task.objects.create(
            company=self.company,
            branch=self.branch,
            title=f"{next_stage} - {next_activity} activity for batch {self.batch.batch_name}",
            description=description,
            due_date=task_due_date,
            assigned_to=activity_owner.owner if activity_owner else None,
            assistant=activity_owner.assistant if activity_owner else None,
            appName="bsf",
            modelName="PondUseStats",
            activity=next_activity,
            status="active",
        )

        return Response(
            {"detail": f"Next task created for {next_activity} activity for batch: {self.batch.batch_name}."},
            status=status.HTTP_201_CREATED,
        )

                    


from twilio.twiml.messaging_response import MessagingResponse
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from twilio.rest import Client
import requests

class WhatsAppTaskViewArchive(APIView):
    """
    Handles WhatsApp task completion messages.
    """
    #authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]  # ✅ Require authentication

    def post(self, request, *args, **kwargs):
        """
        Process WhatsApp messages to start, update, or complete tasks.
        """

        print('how are you')
        sender = request.data.get("From")  # Staff's WhatsApp number
        message = request.data.get("Body", "").strip().lower()  # WhatsApp message body
        media_url = request.data.get("MediaUrl0")  # Media file (if any)
        response = MessagingResponse()

        if "start task" in message:
            task_id = message.split()[-1]
            return self._start_task(task_id, sender, response)

        elif "complete task" in message:
            task_id = message.split()[-1]
            return self._complete_task(task_id, sender, response, media_url)

        elif message.startswith("status"):
            return self._task_status(sender, response)

        response.message("❌ Invalid command. Type 'Start Task <TaskID>' or 'Complete Task <TaskID>'.")
        return Response(str(response), content_type="text/xml")

    def _start_task(self, task_id, sender, response):
        """
        Marks a task as 'in progress' when started via WhatsApp.
        """
        task = Task.objects.filter(id=task_id, assigned_to=sender, status="active").first()
        if not task:
            response.message("❌ Task not found or already started.")
            return Response(str(response), content_type="text/xml")

        task.status = "in_progress"
        task.save()
        response.message(f"✅ Task {task_id} started. Reply with 'Complete Task {task_id}' when finished.")
        return Response(str(response), content_type="text/xml")

    def _complete_task(self, task_id, sender, response, media_url):
        """
        Marks a task as 'completed' via WhatsApp and uploads media if provided.
        """
        task = Task.objects.filter(id=task_id, assigned_to__phone_number=sender, status="in_progress").first()
        if not task:
            response.message("❌ Task not found or not in progress.")
            return Response(str(response), content_type="text/xml")

        task.status = "completed"
        task.completed_by = task.assigned_to
        task.completed_date = now()
        task.completeDetails = "Completed via WhatsApp"
        task.save()

        # Save media if provided
        if media_url:
            media = Media.objects.create(
                title="WhatsApp Upload",
                file=media_url,
                company=task.company,
                model_name="Task",
                model_id=task.id,
                uploaded_by=task.assigned_to,
                status="active"
            )
            media.save()
            response.message("✅ Task completed! Media uploaded.")

        self._create_next_task(task)
        response.message(f"✅ Task {task_id} marked as complete. The next task has been assigned.")
        return Response(str(response), content_type="text/xml")

    def _task_status(self, sender, response):
        """
        Returns the status of active tasks assigned to the sender.
        """
        tasks = Task.objects.filter(assigned_to__phone_number=sender, status__in=["active", "in_progress"])
        if not tasks.exists():
            response.message("✅ You have no pending tasks.")
            return Response(str(response), content_type="text/xml")

        message = "📋 *Your Pending Tasks:*\n"
        for task in tasks:
            message += f"- {task.title} (Due: {task.due_date.strftime('%Y-%m-%d')})\n"
        response.message(message)
        return Response(str(response), content_type="text/xml")

    def _create_next_task(self, task):
        """
        Automatically generates the next task in the workflow.
        """
        next_task_title = f"Next Step After {task.title}"
        next_task = Task.objects.create(
            company=task.company,
            branch=task.branch,
            title=next_task_title,
            description=f"Follow-up after {task.title}.",
            due_date=now() + timedelta(days=2),
            assigned_to=task.assistant if task.assistant else task.assigned_to,
            status="active"
        )
        next_task.save()


class WhatsAppTaskView(APIView):
    """
    Handles WhatsApp task interactions for starting, completing, and notifying users.
    """

    def post(self, request, *args, **kwargs):

        sender = request.data.get("From")
        message = request.data.get("Body", "").strip().lower()
        media_url = request.data.get("MediaUrl0")
        sender_phone = sender.replace("whatsapp:", "").strip()
        #print(f"📩 Incoming WhatsApp Message from {sender}: {message}")

        response = MessagingResponse()

        # ✅ Step 1: Check if the user is logged in via phone
        user = self.get_user_by_phone(sender_phone)

        # ✅ Retrieve stored task ID for continuity
        task_id = cache.get(f"task_{sender_phone}_id", None)

        # ✅ If message contains a task_id, extract it & store it
        extracted_task_id = self.extract_task_id(message)
        if extracted_task_id:
            task_id = extracted_task_id
            cache.set(f"task_{sender_phone}_id", task_id)

        if task_id is None:
            return self.send_message(sender_phone, "❌ No active task found. Please start with 'Start Task <TaskID>'.")
        
        # ✅ Store task_id in cache (ensures continuity)
        #cache.set(f"task_{sender_phone}_id", task_id)

        # ✅ Verify user
        user = self.get_user_by_phone(sender_phone)
        if not user:
            return self.send_message(sender_phone, "❌ No user found with this phone number.")

        # ✅ Process Steps
        return self.process_whatsapp_task_step(sender_phone, message, media_url, task_id)


    def process_whatsapp_task_step(self, sender_phone, message, media_url, task_id):
        """
        Handles step-by-step WhatsApp task data collection dynamically.
        """
        runStep = True  # ✅ Controls whether the loop should continue
       

        while runStep:

            current_step = cache.get(f"whatsapp_step_{sender_phone}", "start_task")
            print(f"🔄 Processing Step: {current_step} for Task {task_id}")

            # ✅ Step 0: Start Task - Ask for End Date
            if current_step == "start_task":
                cache.set(f"whatsapp_step_{sender_phone}", "end_date")
                return self.ask_next_step(sender_phone, "end_date") 

            # ✅ Step 1: Validate & Store End Date
            elif current_step == "end_date":
                if not re.match(r"\d{4}-\d{2}-\d{2}", message):
                    return self.send_message(sender_phone, "❌ Invalid format! Please enter End Date (YYYY-MM-DD).")

                cache.set(f"task_{sender_phone}_end_date", message)
                cache.set(f"whatsapp_step_{sender_phone}", "harvest_weight")
                return self.ask_next_step(sender_phone, "harvest_weight") 
                #current_step = "harvest_weight"
                runStep = True  # ✅ Continue to the next step
                continue  # ✅ Continue loop execution

            # ✅ Step 2: Validate & Store Harvest Weight
            elif current_step == "harvest_weight":
                if not message.isdigit():
                    return self.send_message(sender_phone, "❌ Invalid input! Please enter a numeric Harvest Weight (kg).")

                cache.set(f"task_{sender_phone}_harvest_weight", message)
                cache.set(f"whatsapp_step_{sender_phone}", "harvest_date")
                return self.ask_next_step(sender_phone, "harvest_date") 
                #current_step = "harvest_date"
                runStep = True  # ✅ Continue to the next step
                continue  # ✅ Continue loop execution

            # ✅ Step 3: Validate & Store Harvest Date
            elif current_step == "harvest_date":
                if not re.match(r"\d{4}-\d{2}-\d{2}", message):
                    return self.send_message(sender_phone, "❌ Invalid format! Please enter Harvest Date (YYYY-MM-DD).")

                cache.set(f"task_{sender_phone}_harvest_date", message)
                cache.set(f"whatsapp_step_{sender_phone}", "media")
                return self.ask_next_step(sender_phone, "media") 

            # ✅ Step 4: Collect Media (Optional)
            elif current_step == "media":
                if message.lower() == "skip":
                    cache.set(f"task_{sender_phone}_media", "None")
                elif media_url:
                    cache.set(f"task_{sender_phone}_media", media_url)
                else:
                    return self.send_message(sender_phone, "📸 Upload a photo/video, or type 'SKIP' to continue.")

                
                self.send_message(sender_phone, "✅ Thanks! Submitting Task.....") 
                # ✅ Final Step: Submit the Task
                return self.submit_task(sender_phone, task_id)

        return Response({"message": "Invalid step"}, status=400)

    def get_user_by_phone(self, sender_phone):
        """
        Retrieves the user based on phone number.
        """
        user_profile = UserProfile.objects.filter(phone=sender_phone).first()
        return user_profile.user if user_profile else None

    def _start_task(self, task_id, sender, response):

        """
        Marks a task as 'in progress' when started via WhatsApp.
        """
        # ✅ Extract phone number from 'whatsapp:+17136890771'
        sender_phone = sender.replace("whatsapp:", "").strip()

        # ✅ Retrieve the user based on phone number
        user_profile = UserProfile.objects.filter(phone=sender_phone).first()
        if not user_profile:
            response.message("❌ No user found with this phone number.")
            return Response(str(response), content_type="text/xml")

        user = user_profile.user  # ✅ Get the linked user

        task = Task.objects.filter(id=task_id, status="active").first()
        #print(task)
        if not task:
            response.message("❌ Task not found or already started.")
            return Response(str(response), content_type="text/xml")
        

        # ✅ Start Step 1: Ask for "End Date"
        self.ask_next_step(task_id, sender_phone, step="end_date")
        
        return Response({"message": "Step-by-step WhatsApp form started"}, status=200)
  
    def _complete_task(self, task_id, sender, response, media_url):
        task = Task.objects.filter(id=task_id, assigned_to__work_phone=sender, status="in_progress").first()
        if not task:
            response.message("❌ Task not found or not in progress.")
            return Response(str(response), content_type="text/xml")

        task.status = "completed"
        task.completed_by = task.assigned_to
        task.completed_date = now()
        task.completeDetails = "Completed via WhatsApp"
        task.save()

        if media_url:
            Media.objects.create(
                title="WhatsApp Upload",
                file=media_url,
                company=task.company,
                model_name="Task",
                model_id=task.id,
                uploaded_by=task.assigned_to,
                status="active"
            )

        response.message(f"✅ Task {task_id} completed! You will be notified for the next step.")

        # Notify the manager
        self.notify_manager(task)

        return Response(str(response), content_type="text/xml")

    def notify_manager(self, task):
        """
        Sends a WhatsApp notification to the manager after task completion.
        """
        manager_phone = task.assigned_to.manager.phone_number  # Ensure manager field exists in model
        client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

        message = f"📢 Task {task.id} completed by {task.assigned_to.username}."
        client.messages.create(
            body=message,
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{manager_phone}"
        )

    def extract_task_id(self, message):
        """
        Extracts the task ID from a WhatsApp message.
        Supports different message formats.
        """
        match = re.search(r"task\s+(\d+)", message)
        if match:
            return int(match.group(1))
        return None

    def ask_next_step(self, sender_phone, step):
        """
        Guides the user through the form one step at a time.
        """

        questions = {
            "end_date": "📅 Please enter the *End Date* (YYYY-MM-DD):",
            "harvest_weight": "⚖️ Please enter the *Harvest Weight (kg)*:",
            "harvest_date": "📆 Please enter the *Harvest Date* (YYYY-MM-DD):",
            "media": "📸 Send a *photo or video* (or type SKIP to continue)."
        }

        # ✅ Ask the next question based on `step`
        if step in questions:
            return self.send_message(sender_phone, questions[step])

    def send_message(self, sender_phone, message_body):
        """
        Sends a WhatsApp message to the user.
        """
        TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID")
        TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        client.messages.create(
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{sender_phone}",
            body=message_body
        )

        print(f"📤 Sent WhatsApp Message to {sender_phone}: {message_body}")
        return Response({"message": "WhatsApp message sent"}, status=200)
    
    def submit_task(self, sender_phone, task_id):
        """
        Submits the collected task form data.
        """
        try:

            TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID")
            TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN")
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

            end_date = cache.get(f"task_{sender_phone}_end_date", "")
            harvest_weight = cache.get(f"task_{sender_phone}_harvest_weight", "")
            harvest_date = cache.get(f"task_{sender_phone}_harvest_date", "")
            media = cache.get(f"task_{sender_phone}_media", "")

            # ✅ Submit the task completion data
            form_data = {
                "end_date": end_date,
                "harvest_weight": harvest_weight,
                "harvest_date": harvest_date,
                "media": media
            }

            print(f"📤 Submitting Task Data: {form_data}")

            client.messages.create(
                from_="whatsapp:+14155238886",
                to=f"whatsapp:{sender_phone}",
                body="✅ Task submission complete! Sending for approval."
            )

            # ✅ Ensure response is always returned
            return Response({"message": "Task successfully submitted"}, status=200)
        
        except Exception as e:
            print(f"❌ Error in submit_task: {e}")
            return Response({"error": "Task submission failed"}, status=500)
 

from bsf.whatsapp import PondUseStats_whatsapp  # Import the PondUseStats_whatsapp function
class WhatsAppTaskTest(APIView):
    """
    Handles WhatsApp task interactions for starting, completing, and notifying users.
    """

    def post(self, request, *args, **kwargs):
        processed = {'end_date': '2025-03-10', 'harvest_weight': '5.9', 'pond_name': 'a2', 'status': 'pending', 'media': 'hope'}
        task_id = 55
        user_id = 2
        PondUseStats_whatsapp(task_id, processed, user_id)
        return Response({"message": "WhatsApp task processed"}, status=200)
