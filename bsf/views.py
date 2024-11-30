# views.py
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from .models import Farm, StaffMember
from company.models import Company  # Import the Company model
from .serializers import FarmSerializer, StaffMemberSerializer
from rest_framework.permissions import BasePermission
from company.utils import has_permission



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


class FarmDetailView(generics.ListAPIView):
    """
    Retrieve farms based on query parameters:
    - If `company_id` is provided, return all farms belonging to the company.
    - If `company_id` and `farm_id` are provided, return the specific farm.
    """
    serializer_class = FarmSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffPermission]

    def get_queryset(self):
        # Get query parameters
        company_id = self.request.query_params.get("company")
        farm_id = self.request.query_params.get("farm")

        # Handle missing `company_id`
        if not company_id:
            raise PermissionDenied("A company_id query parameter is required to retrieve farms.")

        # Validate `company_id`
        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            raise PermissionDenied("Invalid company_id provided.")

        # Check user permissions for the company
        if not has_permission(
            user=self.request.user,
            company=company,
            model_name="Farm",
            action="GET"
        ):
            raise PermissionDenied("You do not have permission to view farms for this company.")

        # Filter farms by `farm_id` if provided
        if farm_id:
            return Farm.objects.filter(company=company, id=farm_id)

        # Return all farms for the company
        return Farm.objects.filter(company=company)



class FarmPutViews(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific farm entry.
    """
    queryset = Farm.objects.all()
    serializer_class = FarmSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffPermission]





class StaffMemberListCreateView(generics.ListCreateAPIView):
    """
    List all staff members or assign a new staff member.
    """
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer
    permission_classes = [IsAuthenticatedAndHasPermissionOrSelf]

    def get_queryset(self):
        """
        If the user is accessing their own records, filter by user.
        Otherwise, filter by company or farm based on query parameters.
        """
        user = self.request.user
        if self.request.query_params.get("self", "false").lower() == "true":
            return StaffMember.objects.filter(user=user)

        company_id = self.request.query_params.get("company")
        farm_id = self.request.query_params.get("farm")

        queryset = StaffMember.objects.all()
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if farm_id:
            queryset = queryset.filter(farm_id=farm_id)

        return queryset

    def perform_create(self, serializer):
        """
        Automatically set the `created_by` field to the requesting user.
        """
        serializer.save(created_by=self.request.user)

class StaffMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a specific staff member assignment.
    """
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer
    permission_classes = [IsAuthenticatedAndHasPermissionOrSelf]


