from rest_framework import generics, permissions, serializers  
from .permissions import IsBranchPermission
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from .models import Company, Authority, Staff, StaffLevels, Branch, Media
from .serializers import BranchSerializer
from .serializers import CompanySerializer, AdminCompanySerializer, AuthoritySerializer, StaffSerializer, StaffLevelsSerializer, MediaSerializer
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from company.utils import check_user_exists
from django.apps import apps
import logging


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


# View a specific company or list all companies
class ViewCompanyView(generics.ListAPIView, generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CompanySerializer

    def get_queryset(self):
        """
        Define which companies the user can view.
        - Regular users can view only the companies they created or are linked to.
        - Super admins can view all companies.
        """
        company_id = self.request.headers.get('Company-ID')
        if company_id:
            try:
                company = Company.objects.get(id=company_id)
                if self.request.user.is_superuser or company.creator == self.request.user:
                    return Company.objects.filter(id=company_id)
                else:
                    raise PermissionDenied("You do not have the required permissions to view this company.")
            except Company.DoesNotExist:
                raise PermissionDenied("Company not found.")
        
        if self.request.user.is_superuser:
            return Company.objects.all()
        return Company.objects.filter(creator=self.request.user)
    
    def get_object(self):
        """
        Override get_object to include a permission check using `has_permission`.
        """
        company = super().get_object()  # Get the company object based on the provided ID
        model_name = 'company'  # Replace with the relevant model name
        action = 'view'  # Replace with the desired action (e.g., view)

        # Check if the user has permission to view the company
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have the required permissions to view this company.")

        return company
    
    
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
        company_id = self.kwargs.get('company_id')  # Get company ID from the URL
        staff_id = self.kwargs.get('staff_id')  # Get optional staff ID from the URL

        # Ensure the company exists
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise PermissionDenied("The specified company does not exist.")

        # Check if the user has permission to view staff for this company
        model_name = 'staff'
        action = 'view'
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to view staff for this company.")

        # If a staff ID is provided, filter to a specific staff member
        if staff_id:
            try:
                staff = Staff.objects.get(id=staff_id, company=company)
            except Staff.DoesNotExist:
                raise PermissionDenied("The specified staff member does not exist in this company.")
            return Staff.objects.filter(id=staff.id)

        # Otherwise, return all staff members for the specified company
        return Staff.objects.filter(company=company)

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
    """
    serializer_class = MediaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filters media by company, branch, app_name, and model_name.
        """
        company_id = self.request.query_params.get("company")
        branch_id = self.request.query_params.get("branch")
        app_name = self.request.query_params.get("app_name")
        model_name = self.request.query_params.get("model_name")
        queryset = Media.objects.all()

        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if app_name:
            queryset = queryset.filter(app_name=app_name)
        if model_name:
            queryset = queryset.filter(model_name=model_name)

        return queryset

    def perform_create(self, serializer):
        """
        Validates and creates a new media entry.
        """
        company = serializer.validated_data["company"]
        user = self.request.user

        # Validate user permissions
        if not has_permission(user, company, app_name="company", model_name="Media", action="add"):
            raise PermissionDenied("You do not have permission to add media files for this company.")

        serializer.save(uploaded_by=user)


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
