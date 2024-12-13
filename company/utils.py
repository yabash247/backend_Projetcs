from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied
from .models import Authority, Staff, StaffLevels, Media, Company
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status

User = get_user_model()

# This function is used to save media files associated with a specific model instance.
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
        title = item.get('title')
        file = item.get('file')

        if not title or not file:
            raise ValidationError("Each media entry must include 'title' and 'file'.")

        media_instance = Media.objects.create(
            title=title,
            file=file,
            company=company,
            app_name=app_name,
            model_name=model_name,
            model_id=model_id,
            status='active',
            uploaded_by=user,
        )
        created_media.append(media_instance)

    return created_media

# This function is used to fetch associated media for a specific model instance.
def get_associated_media(data_id, model_name, app_name, company):
    """
    Fetches associated media for the given parameters.
    
    Args:
        data_id (int): The ID of the data item.
        model_name (str): The name of the model to which the media is associated.
        app_name (str): The name of the app where the model resides.
        company (Company): The company associated with the media.

    Returns:
        QuerySet: A queryset of associated Media objects.
    """
    try:
        media_queryset = Media.objects.filter(
            model_id=data_id,
            model_name=model_name,
            app_name=app_name,
            company=company
        )
        print(data_id, model_name, app_name, company)
        return media_queryset
    except ObjectDoesNotExist:
        return Media.objects.none()  # Return an empty queryset if no media is found


# This function is used to check if a user has the required permission to perform a specific action on a model.
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

# This function is used to check if a user exists in the database.
def check_user_exists(user_id: int):
    try:
        user = User.objects.get(email=user_id)
        return True, user
    except User.DoesNotExist:
        return False, None
    

# This function is used to parse media data from a request.
def parse_media_data(request):
    """
    Parse media-related keys from the request and group them by index.

    Args:
        request: The HTTP request containing media data.

    Returns:
        List[Dict]: Parsed media data with indices, titles, files, and comments.
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

def handle_media_uploads(request, data_id, model_name, app_name):
    """
    Handle media uploads for a given data instance.

    Args:
        request: The HTTP request containing media data.
        data_id (int): The ID of the data instance to associate the media with.
        model_name (str): The name of the model associated with the media.
        app_name (str): The app name where the model resides.

    Returns:
        Response: A success or error response.
    """
    company_id = request.data.get("company")
    if not company_id:
        return Response({"detail": "'company' parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

    # Fetch and validate company
    company = get_object_or_404(Company, id=company_id)

    # Parse media data
    media_files = parse_media_data(request)

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
                app_name=app_name,
                model_name=model_name,
                model_id=data_id,
                status="active",
                comments=media_entry["comments"],
                uploaded_by=request.user,
            )
        except Exception as e:
            return Response({"detail": f"Error saving file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({"detail": "Media files uploaded successfully."}, status=status.HTTP_201_CREATED)

