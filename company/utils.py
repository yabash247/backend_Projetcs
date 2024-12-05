from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied
from .models import Authority, Staff, StaffLevels

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

User = get_user_model()

def check_user_exists(user_id: int):
    try:
        user = User.objects.get(email=user_id)
        return True, user
    except User.DoesNotExist:
        return False, None
    


