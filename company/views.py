from rest_framework import generics, permissions, serializers
from .permissions import IsBranchPermission
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from .models import Company, Authority, Staff, StaffLevels, Branch, Media, Task
from django.contrib.auth.models import User
from .serializers import ActivityOwnerSerializer, CompanySerializer, AdminCompanySerializer, AuthoritySerializer, StaffSerializer, StaffLevelsSerializer, MediaSerializer, TaskSerializer, BranchSerializer
from django.shortcuts import get_object_or_404
from company.utils import check_user_exists, get_associated_media, PointsRewardSystem
import logging
from django.apps import apps
from django.utils.timezone import now
from datetime import timedelta
from .models import ActivityOwner
from django.core.mail import send_mail
from django.db.models import Q, F


# Configure logging
logger = logging.getLogger(__name__)

def has_permission(user, company, app_name, model_name, action, min_level=1, requested_documents=None):
    """
    Check if a user has the required authority level for a specific action on a model.

    Parameters:
    - user: The user making the request.
    - company: The company instance the request pertains to.
    - app_name: The target app name (string).
    - model_name: The target model name (string).
    - action: The permission action ('view', 'add', 'edit', 'delete', 'accept', 'approve').
    - min_level: The minimum authority level required (default is 1).
    - requested_documents: A queryset or list of data records being accessed (optional).

    Returns:
    - True if the user is authorized, or a filtered queryset if only partial data is allowed (for 'view' action only).
    - Raises PermissionDenied if no access is granted.
    """

    # Allow superusers or the company creator to execute the request
    if user.is_superuser or company.creator == user:
        return True

    # Check if the user is a staff member of the company
    staff_record = Staff.objects.filter(user=user, company=company).first()
    if not staff_record:
        raise PermissionDenied("You are not a staff member of this company.")

    # Special case: Allow partial access for GET/view actions only
    if action == "view" and requested_documents is not None:
        excluded_models = ["company.Company", "company.Staff", "bsf.StaffMembers"]
        if f"{app_name}.{model_name}" not in excluded_models:  # Model not excluded
            # Filter documents to include only those associated with the logged-in user
            filtered_documents = [
                document
                for document in requested_documents
                if hasattr(document, 'user') and document.user == user
            ]

            # If filtered documents exist and the user matches, allow partial access
            if filtered_documents:
                return filtered_documents

    # Check if the app_name and model_name exist in the Authority model
    authority = Authority.objects.filter(company=company, app_name=app_name, model_name=model_name).first()
    if not authority:
        # If not defined in Authority, allow request for superusers or company creator
        if user.is_superuser or company.creator == user:
            return True

    # Get the required authority level for the specified action
    try:
        required_level = int(getattr(authority, action, '5'))  # Default to the highest level if undefined
    except AttributeError:
        raise PermissionDenied(f"Invalid action '{action}'.")

    # Ensure the staff has the required authority level
    staff_level = StaffLevels.objects.filter(user=user, company=company).values_list('level', flat=True).first()
    if not staff_level or int(staff_level) < required_level or int(staff_level) < min_level:
        raise PermissionDenied(f"Insufficient authority level to perform the '{action}' action.")

    return True

# *******  Views for Authority Model ***********
class AuthorityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        """
        Retrieve all authority settings for the specified company
        and notify about models not included in the authority model.
        """
        company = get_object_or_404(Company, id=company_id)

        # Access control
        user = request.user
        if not (
            user.is_superuser or
            user == company.creator or
            has_permission(user, company, app_name="company", model_name="Authority", action="view")
        ):
            raise PermissionDenied("You do not have access to this resource.")

        # Get all registered models for all apps, excluding specific apps
        excluded_apps = ['admin', 'auth', 'contenttypes', 'sessions', 'token_blacklist', 'account', 'socialaccount', 'otp_totp']
        all_models = []
        for app_config in apps.get_app_configs():
            app_name = app_config.label
            if app_name not in excluded_apps:  # Skip excluded apps
                for model in app_config.get_models():
                    all_models.append({"app_name": app_name, "model_name": model.__name__})

        # Get models already in the Authority model for this company
        authority_models = Authority.objects.filter(company=company).values_list('app_name', 'model_name')
        missing_models = [
            model for model in all_models
            if (model["app_name"], model["model_name"]) not in authority_models
        ]

        authorities = Authority.objects.filter(company=company)
        serializer = AuthoritySerializer(authorities, many=True)

        return Response({
            "authorities": serializer.data,
            "missing_models": missing_models
        })

    def post(self, request, company_id):
        """
        Add a new authority entry for the specified company.
        """
        company = get_object_or_404(Company, id=company_id)

        # Access control
        user = request.user
        data = request.data
        app_name = data.get('app_name')
        model_name = data.get('model_name')
        if not has_permission(user, company, app_name=app_name, model_name=model_name, action="add"):
            raise PermissionDenied("You do not have permission to add authority settings.")

        data['company'] = company.id
        serializer = AuthoritySerializer(data=data)
        if serializer.is_valid():
            serializer.save(requested_by=user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

class AddAuthorityView(generics.CreateAPIView):
    serializer_class = AuthoritySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        company = serializer.validated_data['company']
        app_name = serializer.validated_data['app_name']
        model_name = serializer.validated_data['model_name']
        action = 'add'  # Action for this endpoint

        # Check permissions
        if not has_permission(self.request.user, company, app_name=app_name, model_name=model_name, action=action):
            raise PermissionDenied("You do not have permission to add an authority.")

        serializer.save(requested_by=self.request.user)

class EditAuthorityView(RetrieveUpdateAPIView):
    """
    View to retrieve and update an authority record.
    Ensures that app_name and model_name cannot be changed during updates.
    """
    serializer_class = AuthoritySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Defines the queryset for retrieving authority records.
        """
        return Authority.objects.all()

    def perform_update(self, serializer):
        """
        Custom logic for updating an authority record.
        Ensures that app_name and model_name cannot be changed.
        """
        authority = self.get_object()  # Retrieve the current authority record
        company = authority.company
        app_name = authority.app_name
        model_name = authority.model_name
        action = 'edit'  # Action being performed

        # Check if the requesting user has the appropriate permissions
        if not has_permission(self.request.user, company, app_name=app_name, model_name=model_name, action=action):
            raise PermissionDenied("You do not have permission to edit this authority.")

        # Prevent changing model_name during update
        if 'model_name' in serializer.validated_data and serializer.validated_data['model_name'] != model_name:
            raise serializers.ValidationError({"model_name": "Changing the model_name is not allowed."})

        # Prevent changing app_name during update
        if 'app_name' in serializer.validated_data and serializer.validated_data['app_name'] != app_name:
            raise serializers.ValidationError({"app_name": "Changing the app_name is not allowed."})

        # Save the updated record with the requested_by field set to the current user
        serializer.save(requested_by=self.request.user)

class DeleteAuthorityView(generics.DestroyAPIView):
    serializer_class = AuthoritySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Authority.objects.all()

    def perform_destroy(self, instance):
        company = instance.company
        app_name = instance.app_name
        model_name = instance.model_name
        action = 'delete'  # Action for this endpoint

        # Check permissions
        if not has_permission(self.request.user, company, app_name=app_name, model_name=model_name, action=action):
            raise PermissionDenied("You do not have permission to delete this authority.")

        instance.delete()


class apiTest(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Allocate points for a completed task.
        """
        try:
            # Initialize PointsRewardSystem with the request data
            reward_system = PointsRewardSystem(request)

            # Allocate points
            allocation_result = reward_system.allocate_points(reward_system.staff, reward_system.task)

            return Response(allocation_result, status=200 if allocation_result["status"] == "pending" else 400)
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=403)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)
        except Exception as e:
            return Response({"error": "An unexpected error occurred."}, status=500)


# *******  Views for Company Model ***********

class ViewCompanyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Fetch `company` parameter from request query params
        company_id = request.query_params.get('company')

        if company_id:
            # Validate the provided company ID
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                raise NotFound("The provided Company ID is not valid or does not exist.")

            # Check permissions using the `has_permission` utility
            if not has_permission(
                user=request.user,
                company=company,
                app_name="company",
                model_name="Company",
                action="view"
            ):
                raise PermissionDenied("You do not have the required permissions to view this company.")

            # Fetch associated media for the company
            media_queryset = get_associated_media(
                data_id=company.id,
                model_name="Company",
                app_name="company",
                company=company
            )
            media_serializer = MediaSerializer(media_queryset, many=True)

            # Serialize company data
            company_serializer = CompanySerializer(company)

            return Response({
                "company": company_serializer.data,
                "media": media_serializer.data
            })

        else:
            # Handle multiple companies retrieval
            if request.user.is_superuser:
                queryset = Company.objects.all()
            else:
                queryset = Company.objects.filter(creator=request.user)

            companies_data = []

            for company in queryset:
                # Fetch associated media for each company
                media_queryset = get_associated_media(
                    data_id=company.id,
                    model_name="Company",
                    app_name="company",
                    company=company
                )
                media_serializer = MediaSerializer(media_queryset, many=True)

                # Serialize company data
                company_serializer = CompanySerializer(company)

                # Append data to the list
                companies_data.append({
                    "company": company_serializer.data,
                    "media": media_serializer.data
                })

            return Response({"companies": companies_data})

class AddCompanyView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CompanySerializer

    def perform_create(self, serializer):
        # Set the current user as the creator and enforce default status
        serializer.save(creator=self.request.user)

class EditCompanyView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        # Use the admin serializer for super admins
        if self.request.user.is_superuser:
            return AdminCompanySerializer
        return CompanySerializer

    def get_queryset(self):
        # Ensure only super admins can edit status
        return Company.objects.all()

    def perform_update(self, serializer):
        if not self.request.user.is_superuser and 'status' in serializer.validated_data:
            raise PermissionDenied("Only super admins can change the status.")
        serializer.save()

class DeleteCompanyView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Company.objects.filter(creator=self.request.user)



# *******  Views for Staff Model ***********



class ViewStaffView(generics.ListAPIView):
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter staff by company or retrieve a specific staff member.
        """
        company_id = self.kwargs.get('company_id')  # Get company ID from URL
        staff_id = self.kwargs.get('staff_id')  # Get optional staff ID from URL

        # ✅ Ensure the company exists
        company = get_object_or_404(Company, id=company_id)

        # ✅ Check if user has permission
        if not has_permission(
                user=self.request.user,
                company=company,
                app_name="company",
                model_name="Staff",
                action="view"
            ):
            raise PermissionDenied("You do not have permission to view staff for this company.")

        # ✅ If a staff ID is provided, return a specific staff member with annotation
        if staff_id:
            return Staff.objects.filter(id=staff_id, company=company).select_related("user")

            # ✅ Fetch reward details (optional)
            rewards_data = staff.get_max_reward_points_and_value()
            #print(f"Max Points: {rewards_data['max_points']}, Currency: {rewards_data['currency_symbol']}, Value: {rewards_data['value_in_currency']}")

            
        # ✅ Otherwise, return all staff members for the company with annotations
        return Staff.objects.filter(company=company).select_related("user")


class AddStaffView(generics.CreateAPIView):
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated]


    def perform_create(self, serializer):
        
        # Extract company and user data
        company = serializer.validated_data['company']
        #user = serializer.validated_data['user']
        action = 'add'  # The action for this endpoint is 'add'
        model_name = 'staff'  # Assuming the model name is 'staff'
        user_id = serializer.validated_data['user']

        # Check if the specified user exists
        user_exists, userData = check_user_exists(user_id)
        if not user_exists:
            raise PermissionDenied("The specified user does not exist.")

        # Ensure the user performing the request has permission to add staff
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to add staff to this company.")

        # Check if the user is already a staff member of the company
        if Staff.objects.filter(user=user_id, company=company).exists():
            raise ValidationError("This user is already a staff member of the specified company.")

        # Use the user's email if no work_email is provided
        work_email = serializer.validated_data.get('work_email', userData.email)

        # Automatically set the added_by and approved_by fields to the authenticated user
        serializer.save(added_by=self.request.user, approved_by=self.request.user, work_email=work_email)


class EditStaffView(generics.RetrieveUpdateAPIView):
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Staff.objects.all()

    def perform_update(self, serializer):
        staff = self.get_object()
        company = staff.company
        action = 'edit'  # The action for this endpoint is 'edit'
        model_name = 'staff'  # Assuming the model name is 'staff'

        # Check if the user has permission to edit the staff
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to edit this staff record.")

        # Automatically set the requested_by field to the authenticated user
        serializer.save(added_by=self.request.user, approved_by=self.request.user)

class DeleteStaffView(generics.DestroyAPIView):
    serializer_class = StaffSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Staff.objects.all()

    def perform_destroy(self, instance):
        company = instance.company
        action = 'delete'  # The action for this endpoint is 'delete'
        model_name = 'staff'  # Assuming the model name is 'staff'

        # Check if the user has permission to delete the staff
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to delete this staff record.")

        instance.delete()



# *******  Views for Staff Level Model ***********
class AddStaffLevelView(generics.CreateAPIView):
    serializer_class = StaffLevelsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Ensure the user has the permission to add a staff level
        company = serializer.validated_data['company']
        action = 'add'  # The action for this endpoint is 'add'
        model_name = 'stafflevels'  # Assuming the model name is 'stafflevels'
        user_id = serializer.validated_data['user_id']

        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to add a staff level to this company.")
        
        # Check if the specified user exists
        user_exists, user = check_user_exists(user_id)
        if not user_exists:
            raise PermissionDenied("The specified user does not exist.")

        # Check if the specified user is a staff member of the company
        if not Staff.objects.filter(user=user, company=company).exists():
            raise PermissionDenied("The specified user is not a staff member of this company.")

        # Automatically set the approver field to the authenticated user
        logger.debug(f"Saving serializer with data: {serializer.validated_data}")
        serializer.save(approver=self.request.user)

class EditStaffLevelView(generics.RetrieveUpdateAPIView):
    serializer_class = StaffLevelsSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'  # Use 'id' to look up the StaffLevels instance

    def get_queryset(self):
        return StaffLevels.objects.all()

    def get_serializer(self, *args, **kwargs):
        # Get the serializer instance
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        
        # If updating, exclude the 'user' field
        if self.request.method in ['PUT', 'PATCH']:
            kwargs['partial'] = True
            serializer = serializer_class(*args, **kwargs)
            serializer.fields.pop('user', None)
            return serializer
        
        return serializer_class(*args, **kwargs)

    def perform_update(self, serializer):
        # Ensure the user has the permission to edit the staff level
        company = serializer.validated_data.get('company', self.get_object().company)
        action = 'edit'  # The action for this endpoint is 'edit'
        model_name = 'stafflevels'  # Assuming the model name is 'stafflevels'
        specified_user = serializer.validated_data.get('user', self.get_object().user)

        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to edit this staff level.")

        # Check if the specified user is a staff member of the company
        if not Staff.objects.filter(user=specified_user, company=company).exists():
            raise PermissionDenied("The specified user is not a staff member of this company.")

        # Log the data being updated
        logger.debug(f"Updating serializer with data: {serializer.validated_data}")
        
        # Perform the update
        serializer.save()

class DeleteStaffLevelView(generics.DestroyAPIView):
    serializer_class = StaffLevelsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StaffLevels.objects.all()

    def perform_destroy(self, instance):
        company = instance.company
        action = 'delete'  # The action for this endpoint is 'delete'
        model_name = 'stafflevels'  # Assuming the model name is 'stafflevels'

        # Check if the user has permission to delete the staff level
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to delete this staff level record.")

        instance.delete()
       
class StaffLevelView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id, user_id):
        # Authenticate user and retrieve the company
        company = get_object_or_404(Company, id=company_id)
        user = request.user

        # Check user permissions
        if not (
            user.is_superuser or
            user == company.creator or
            (Staff.objects.filter(user=user, company=company).exists() and
             Staff.objects.get(user=user, company=company).has_permission())
        ):
            raise PermissionDenied("You do not have access to this resource.")

        # Get staff level information
        staff_level = StaffLevels.objects.filter(company=company_id, user=user_id).first()
        if not staff_level:
            raise NotFound(f"Staff level data not found for user {user_id} in company {company_id}.")

        # Serialize and return the data
        serializer = StaffLevelsSerializer(staff_level)
        return Response(serializer.data)
    

class BranchListCreateView(generics.ListCreateAPIView):
    """
    List all branches or create a new branch.
    """
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, IsBranchPermission]

    def get_queryset(self):
        # Optionally filter by company if provided in query parameters
        company_id = self.request.query_params.get("company")
        if company_id:
            return Branch.objects.filter(company_id=company_id)
        return super().get_queryset()

class BranchDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific branch.
    """
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, IsBranchPermission]

    def get_queryset(self):
        """
        Override to include app_name in the queryset filtering process.
        """
        app_name = self.request.query_params.get("app_name")
        company_id = self.request.query_params.get("company")
        if not app_name or not company_id:
            raise PermissionDenied("Both 'app_name' and 'company' are required.")

        user = self.request.user
        company = get_object_or_404(Company, id=company_id)

        # Ensure the user has permission
        if not has_permission(user, company, app_name=app_name, model_name="Branch", action="view"):
            raise PermissionDenied("You do not have permission to view this branch.")

        return Branch.objects.filter(company=company, appName=app_name)

    def perform_update(self, serializer):
        """
        Override to validate permissions and include `app_name` during the update.
        """
        app_name = self.request.data.get("app_name")
        company = serializer.validated_data.get("company")
        user = self.request.user

        if not app_name:
            raise PermissionDenied("The 'app_name' field is required.")

        # Validate user permissions
        if not has_permission(user, company, app_name=app_name, model_name="Branch", action="edit"):
            raise PermissionDenied("You do not have permission to edit this branch.")

        serializer.save()

    def perform_destroy(self, instance):
        """
        Override to validate permissions and include `app_name` during deletion.
        """
        app_name = self.request.query_params.get("app_name")
        user = self.request.user
        company = instance.company

        if not app_name:
            raise PermissionDenied("The 'app_name' field is required.")

        # Validate user permissions
        if not has_permission(user, company, app_name=app_name, model_name="Branch", action="delete"):
            raise PermissionDenied("You do not have permission to delete this branch.")

        instance.delete()


class MediaListCreateView(generics.ListCreateAPIView):
    """
    View to list all media files or upload a new media file.

    Filters:
    - `company`: Filter by company ID.
    - `branch`: Filter by branch ID.
    - `app_name`: Filter by application name.
    - `model_name`: Filter by model name.

    Permission:
    - User must be authenticated.
    - User must have the `add` permission for the `Media` model.
    """
    serializer_class = MediaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Retrieves media entries filtered by the specified query parameters.
        """
        queryset = Media.objects.all()
        company_id = self.request.query_params.get("company")
        branch_id = self.request.query_params.get("branch")
        app_name = self.request.query_params.get("app_name")
        model_name = self.request.query_params.get("model_name")

        filters = Q()
        if company_id:
            filters &= Q(company_id=company_id)
        if branch_id:
            filters &= Q(branch_id=branch_id)
        if app_name:
            filters &= Q(app_name=app_name)
        if model_name:
            filters &= Q(model_name=model_name)

        queryset = queryset.filter(filters)
        return queryset

    def perform_create(self, serializer):
        """
        Validates and creates a new media entry.

        Raises:
        - PermissionDenied: If the user does not have permission to add media.
        """
        company = serializer.validated_data.get("company")
        user = self.request.user

        # Validate user permissions
        if not has_permission(user, company, app_name="company", model_name="Media", action="add"):
            raise PermissionDenied("You do not have permission to add media files for this company.")

        try:
            serializer.save(uploaded_by=user)
        except Exception as e:
            raise PermissionDenied(f"An error occurred while saving the media: {str(e)}")

class MediaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View to retrieve, update, or delete a media file.
    """
    serializer_class = MediaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Media.objects.all()

    def perform_update(self, serializer):
        """
        Validates and updates a media file.
        """
        company = serializer.validated_data["company"]
        user = self.request.user

        # Validate user permissions
        if not has_permission(user, company, app_name="company", model_name="Media", action="edit"):
            raise PermissionDenied("You do not have permission to edit this media file.")

        serializer.save()

    def perform_destroy(self, instance):
        """
        Validates and deletes a media file.
        """
        company = instance.company
        user = self.request.user

        # Validate user permissions
        if not has_permission(user, company, app_name="company", model_name="Media", action="delete"):
            raise PermissionDenied("You do not have permission to delete this media file.")

        instance.delete()


class TaskListCreateView(generics.ListCreateAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Fetch tasks based on user, company, branch, status query parameters,
        and annotate late task information if the user is an assistant.
        Include tasks late by 2 days or more if the user is a branch staff.
        """
        user = self.request.user # Get the authenticated user
        queryset = Task.objects.all() # Get all tasks

        # Handle query parameters
        all_param = self.request.query_params.get("all", "false").lower() == "true"
        owner_param = self.request.query_params.get("owner", "false").lower() == "true"
        assistant_param = self.request.query_params.get("assistant", "false").lower() == "true"
        manager_param = self.request.query_params.get("manager", "false").lower() == "true"
        company_id = self.request.query_params.get("company")
        branch_id = self.request.query_params.get("branch")
        status_param = self.request.query_params.get("status")

        if manager_param:
            # Initialize an empty query filter
            member_query_filter = Q()

            

            # Filter tasks where the user is a manager
            for task in queryset:

                app_name = task.appName
                # Get the StaffMember model (assumes app_name is constant or known)
                StaffMemberModel = apps.get_model(app_name, 'StaffMember')  # Replace 'app_name' with actual app name


                if StaffMemberModel.objects.filter(user=task.assigned_to, leader=user).exists():
                    #print(f"User is a manager of {task.assigned_to}")
                    member_query_filter |= Q(assigned_to=task.assigned_to)

            # Apply the accumulated filter to the queryset
            member_querySet = queryset.filter(member_query_filter)

            return member_querySet
        
    
        if all_param:
            # also check if user is a manager of the farm***.

            if branch_id and not company_id:
                raise ValidationError("'company' is required when 'branch' is provided.")

            if company_id:
                try:
                    company = Company.objects.get(id=company_id)
                except Company.DoesNotExist:
                    raise ValidationError(f"Company with ID '{company_id}' does not exist.")

                if not has_permission(user, company, app_name="bsf", model_name="Task", action="view"):
                    raise PermissionDenied("You do not have permission to view tasks for this company.")

                queryset = queryset.filter(company=company)

                if branch_id:
                    try:
                        branch = Branch.objects.get(branch_id=branch_id)
                    except Branch.DoesNotExist:
                        raise ValidationError(f"Branch with ID '{branch_id}' does not exist.")

                    if branch.company != company:
                        raise ValidationError(f"Branch '{branch.name}' does not belong to Company '{company.name}'.")

                    queryset = queryset.filter(branch=branch)
       

        elif owner_param:
            # Get all tasks where the user is the owner
            queryset = queryset.filter(owner=user)

        elif assistant_param:
            # Get all tasks where the user is the assistant
            queryset = queryset.filter(assistant=user)
            
        else:
            # Get all tasks assigned to the user
            queryset = queryset.filter(assigned_to=user)

            # Get all late tasks where the user is an assistant
            late_tasks = Task.objects.filter(
                due_date__lt=now() - timedelta(days=1),
                status="active",
                assistant=user
            )
            queryset = queryset | late_tasks  # Combine the two querysets

        
        # Include extra tasks delayed by 2 or more days for branch staff
        delayed_tasks = Task.objects.filter(
            due_date__lt=now() - timedelta(days=2),
            status="active"
        )

        for task in delayed_tasks:
            appName = task.appName
            # Check if the user is an active staff member of the branch
            StaffMemberModel = apps.get_model(appName, 'StaffMember')
            if StaffMemberModel.objects.filter(user=user, status="active", company=task.company).exists():
                queryset = queryset | delayed_tasks 
        
        # Filter by task completion and ownership
        completed_tasks = Task.objects.exclude(status="active")
        user_completed_tasks = completed_tasks.filter(completed_by=user)
        other_completed_tasks = completed_tasks.exclude(completed_by=user)
        queryset = queryset | user_completed_tasks
        queryset = queryset.exclude(pk__in=other_completed_tasks.values_list('pk', flat=True))

        # Filter by status
        if status_param:
            valid_status_choices = [choice[0] for choice in Task.STATUS_CHOICES]
            if status_param not in valid_status_choices:
                raise ValidationError({"status": f"Invalid status '{status_param}'. Valid options are: {', '.join(valid_status_choices)}."})
            queryset = queryset.filter(status=status_param)

        
        if company_id:# If company is provided in param:
                try:
                    company = Company.objects.get(id=company_id)
                except Company.DoesNotExist: # Check if company exist
                    raise ValidationError(f"Company with ID '{company_id}' does not exist.")
                if not has_permission(user, company, app_name="bsf", model_name="Task", action="view"):
                    raise PermissionDenied("You do not have permission to view tasks for this company.")
                if branch_id:
                    try: 
                        branch = Branch.objects.get(branch_id=branch_id)
                    except Branch.DoesNotExist:
                            raise ValidationError(f"Branch with ID '{branch_id}' does not exist.")
                    if branch :
                        queryset = queryset.filter(branch=branch)
                queryset = queryset.filter(company=company)

        # Annotate each task with associated_activity
        tasks_with_activity = []
        for task in queryset:
            associated_activity = ActivityOwner.objects.filter(
                branch=task.branch,
                activity=task.activity,
                appName=task.appName,
                modelName=task.modelName,
                company=task.company,
            ).first()
            task_data = TaskSerializer(task).data  # Serialize task data
            if associated_activity:
                task_data["associated_activity"] = ActivityOwnerSerializer(associated_activity).data
            else:
                task_data["associated_activity"] = None
            tasks_with_activity.append(task_data)

        return tasks_with_activity
    
    def list(self, request, *args, **kwargs):
        """
        Override the list method to return the annotated queryset as a response.
        """
        queryset = self.get_queryset()
        return Response(queryset)

    
        #return queryset

    def perform_create(self, serializer):
        #**** Create Custom Task 
        serializer.save()

class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]


# create custom task 

class CustomTaskView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Create a custom task for the authenticated user.
        """
        data = request.data

        
        # Validate the request data
        serializer = TaskSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        
        # Ensure the user has permission to create a custom task
        company = data.get("company")
        app_name = data.get("appName")
        model_name = data.get("modelName")
        action = 'add'  # The action for this endpoint is 'add'

        if not has_permission(request.user, company, app_name, model_name, action):
            raise PermissionDenied("You do not have permission to create a custom task.")

        # Create the custom task
        task = Task.objects.create(
            title=data.get("title"),
            due_date=data.get("due_date"),
            assigned_to=data.get("owner"),
            status="active",
            company=data.get("company"),
            branch=data.get("branch"),
            appName=data.get("appName"),
            modelName=data.get("modelName"),
            description=data.get("description", ""),
            assistant=data.get("assistant", None),
            activity = data.get("activity", None),
        )

        # Serialize and return the task data
        serializer = TaskSerializer(task)
        return Response(serializer.data, status=201)

class ActivityOwnerListCreateView(generics.ListCreateAPIView):
    queryset = ActivityOwner.objects.all().order_by('-created_date')
    serializer_class = ActivityOwnerSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class ActivityOwnerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ActivityOwner.objects.all()
    serializer_class = ActivityOwnerSerializer
    permission_classes = [IsAuthenticated]

class Recurance(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("You do not have permission to perform this action.")

        nowTime = now()
        activities = ActivityOwner.objects.filter(status="active", reoccurring=True)
        # print(f"Checking for activities at {now}")

        for activity in activities:
            # check if activity is on-going (activity.start_date <= now <= activity.start_date + activity.interval_days)
            if activity.reoccurring_Start and activity.reoccurring_Start <= nowTime.date() and nowTime.date() <= (activity.reoccurring_Start + timedelta(days=activity.interval_days)):
                print(f"Activity {activity.activity} is on-going.")
                continue
            # Check if the activity is due for reoccurring task creation
            elif activity.reoccurring_End is None or activity.reoccurring_End > nowTime:
                print(f"Creating task for activity {activity.activity} - {activity.owner}")
                # Generate new task

                # Create the next task in the workflow
                Task.objects.create(
                    company=activity.company,
                    branch=activity.branch,
                    title=f"{activity.activity} - {activity.owner}",
                    due_date=(activity.reoccurring_End or nowTime) + timedelta(days=activity.interval_days),
                    assigned_to=activity.owner if activity else None,
                    assistant=activity.assistant if activity else None,
                    appName=activity.appName,
                    modelName=activity.modelName,
                    activity=activity.activity,
                    status="active",
                )
                print(f"Created task for activity {activity.activity} - {activity.owner}")

                #update reoccurring_Start time 
                activity.reoccurring_Start = nowTime
                activity.save()

            # need to send an email to activity owner manager inform that activity is due for reoccurring task creation but still has one that isn't completed yet
            else:
                # Send an email to the activity owner's manager

                # Get the manager's email
                manager_email = activity.owner.manager.email if activity.owner.manager else None

                if manager_email:
                    send_mail(
                        subject="Reoccurring Task-{activity.activity}, Creation Due",
                        message=f"Dear Manager,\n\nThe activity '{activity.activity}' assigned to {activity.owner} is due for reoccurring task creation but still has one that isn't completed yet.\n\nPlease take the necessary actions.\n\nBest regards,\nYour Company",
                        from_email="no-reply@yourcompany.com",
                        recipient_list=[manager_email],
                        fail_silently=False,
                    )

                print(f"Activity {activity.activity} is due for reoccurring task creation but still has one that isn't completed yet.")
                continue

        return Response({"message": "Reoccurring tasks created successfully."})
    
