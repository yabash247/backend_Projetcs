from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied
from .models import Authority, Staff, StaffLevels

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


User = get_user_model()

def check_user_exists(user_id: int):
    try:
        user = User.objects.get(email=user_id)
        return True, user
    except User.DoesNotExist:
        return False, None
    


