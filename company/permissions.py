from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from company.models import Company
from company.utils import has_permission


class IsBranchPermission(BasePermission):
    """
    Custom permission to validate if the user has permission to access or modify a branch.
    """
    def has_permission(self, request, view):
        # Ensure the user is authenticated
        if not request.user.is_authenticated:
            return False

        # Determine action based on HTTP method
        action = request.method  # GET, POST, PUT, DELETE, etc.

        # Get the `app_name` from request data or query params
        app_name = request.data.get("app_name") or request.query_params.get("app_name")
        if not app_name:
            raise PermissionDenied("App name must be provided.")

        if action in ["GET", "POST"]:  # For listing or creating branches
            company_id = request.data.get("company") or request.query_params.get("company")
            if not company_id:
                raise PermissionDenied("Company ID must be provided.")

            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                raise PermissionDenied("Invalid Company ID.")

            # Pass the `Company` object and `app_name` to `has_permission`
            return has_permission(
                user=request.user,
                company=company,
                app_name=app_name,
                model_name="Branch",
                action=action
            )

        return True

    def has_object_permission(self, request, view, obj):
        # Ensure the user has permission to view or modify the specific branch
        action = request.method  # GET, PUT, DELETE, etc.

        # Get the `app_name` from request data or query params
        app_name = request.data.get("app_name") or request.query_params.get("app_name")
        if not app_name:
            raise PermissionDenied("App name must be provided.")

        return has_permission(
            user=request.user,
            company=obj.company,  # Pass the Company object
            app_name=app_name,
            model_name="Branch",
            action=action
        )
