from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Company, Authority, Staff, StaffLevels
from .serializers import CompanySerializer, AdminCompanySerializer, AuthoritySerializer, StaffSerializer, StaffLevelsSerializer
from django.shortcuts import get_object_or_404

def has_permission(user, company, model_name, action, min_level=1):
    """
    Check if a user has the required authority level for a specific action on a model.
    
    Parameters:
    - user: The user making the request.
    - company: The company instance the request pertains to.
    - model_name: The target model name (string).
    - action: The permission action ('view', 'add', 'edit', 'delete', 'accept', 'approve').
    - min_level: The minimum authority level required (default is 1).

    Returns:
    - True if the user is authorized; raises PermissionDenied otherwise.
    """

    # Allow superusers or the company creator to execute the request
    if user.is_superuser or company.creator == user:
        return True

    # Check if the user is a staff member of the company
    staff_record = Staff.objects.filter(user=user, company=company).first()
    if not staff_record:
        raise PermissionDenied("You are not a staff member of this company.")

    # Check if the model_name exists in the Authority model
    authority = Authority.objects.filter(company=company, model_name=model_name).first()
    if not authority:
        # If model_name is not defined in Authority, allow request for superusers or company creator
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
        # Retrieve the company instance
        company = get_object_or_404(Company, id=company_id)

        # Access control
        user = request.user
        if not (
            user.is_superuser or 
            user == company.creator or 
            (Staff.objects.filter(user=user, company=company).exists() and
             Staff.objects.get(user=user, company=company).has_permission())
        ):
            raise PermissionDenied("You do not have access to this resource.")

        # Filter Authority objects by the provided company ID
        authorities = Authority.objects.filter(company=company)
        serializer = AuthoritySerializer(authorities, many=True)
        return Response(serializer.data)


class AddAuthorityView(generics.CreateAPIView):
    serializer_class = AuthoritySerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Ensure the user has the permission to add an authority
        company = serializer.validated_data['company']
        model_name = serializer.validated_data['model_name']
        action = 'add'  # The action for this endpoint is 'add'

        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to add an authority.")

        # Automatically set the requested_by field to the authenticated user
        serializer.save(requested_by=self.request.user)

class EditAuthorityView(generics.RetrieveUpdateAPIView):
    serializer_class = AuthoritySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Authority.objects.all()

    def perform_update(self, serializer):
        authority = self.get_object()
        company = authority.company
        model_name = authority.model_name
        action = 'edit'  # The action for this endpoint is 'edit'

        # Check if the user has permission to edit the authority
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to edit this authority.")

        # Automatically set the requested_by field to the authenticated user
        serializer.save(requested_by=self.request.user)

class DeleteAuthorityView(generics.DestroyAPIView):
    serializer_class = AuthoritySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Authority.objects.all()

    def perform_destroy(self, instance):
        company = instance.company
        model_name = instance.model_name
        action = 'delete'  # The action for this endpoint is 'delete'

        # Check if the user has permission to delete the authority
        if not has_permission(self.request.user, company, model_name, action):
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
        user = serializer.validated_data['user']
        action = 'add'  # The action for this endpoint is 'add'
        model_name = 'staff'  # Assuming the model name is 'staff'

        # Ensure the user performing the request has permission to add staff
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to add staff to this company.")

        # Check if the user is already a staff member of the company
        if Staff.objects.filter(user=user, company=company).exists():
            raise ValidationError("This user is already a staff member of the specified company.")

        # Automatically set the added_by field to the authenticated user
        serializer.save(added_by=self.request.user, approved_by=self.request.user)

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

        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to add a staff level to this company.")
        
        # Check if the target user is a staff member of the company
        if not Staff.objects.filter(user=self.request.user, company=company).exists():
            raise PermissionDenied("The specified user is not a staff member of this company.")

        # Automatically set the approver field to the authenticated user
        serializer.save(approver=self.request.user)


class EditStaffLevelView(generics.RetrieveUpdateAPIView):
    serializer_class = StaffLevelsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StaffLevels.objects.all()

    def perform_update(self, serializer):
        staff_level = self.get_object()
        company = staff_level.company
        action = 'edit'  # The action for this endpoint is 'edit'
        model_name = 'stafflevels'  # Assuming the model name is 'stafflevels'

        # Check if the user has permission to edit the staff level
        if not has_permission(self.request.user, company, model_name, action):
            raise PermissionDenied("You do not have permission to edit this staff level record.")

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
