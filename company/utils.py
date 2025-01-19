from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied
from .models import Authority, Staff, StaffLevels, Media, Company, Branch, RewardsPointsTracker, Task, Media, ActivityOwner
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from django.apps import apps
import logging
from django.core.mail import send_mail


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


from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS
import mimetypes

def handle_file(media_file,  allowed_types):
    try:
        mime_type, _ = mimetypes.guess_type(media_file.name)
        if mime_type in ["image/png"]:
            print(f"Skipping EXIF for {media_file.name} (PNG file)")
            return  # PNG files do not have EXIF data

        image = Image.open(media_file)
        exif_data = image._getexif()  # Attempt to retrieve EXIF data

        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                print(f"{tag}: {value}")
    except UnidentifiedImageError:
        print(f"File {media_file.name} is not a valid image.")
    except AttributeError:
        print(f"File {media_file.name} does not have EXIF data.")

ALLOWED_TYPES = ["video/mp4", "image/jpeg", "image/png"]
def is_valid_file(media_file):
    mime_type, _ = mimetypes.guess_type(media_file.name)
    if mime_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported file type: {mime_type}")
    return True


import os
from django.conf import settings

def save_uploaded_file(media_file, destination_dir):
    """
    Save an uploaded file to a specific directory.
    """
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)

    file_path = os.path.join(destination_dir, media_file.name)
    with open(file_path, 'wb+') as destination:
        for chunk in media_file.chunks():
            destination.write(chunk)
    return file_path



from django.utils.timezone import now
from django.db.models import Sum

class PointsRewardSystem:
    def __init__(self, request):
        """
        Initialize the reward system with dynamic maximum monthly points for the staff.

        Args:
            staff (Staff): The staff member for whom the reward system is initialized.
        """

        self.request = request

        # Validate and fetch company, branch, and staff instances
        company_id = request.data.get("company")
        branch_id = request.data.get("branch")
        user_id = request.data.get("staff")
        task_id=request.data.get("task")

        if not company_id:
            raise PermissionDenied("The 'company' query parameter is required.")
        if not branch_id:
            raise PermissionDenied("The 'branch' query parameter is required.")
        if not user_id:
            raise PermissionDenied("The 'staff' query parameter is required.")
        if not task_id:
            raise PermissionDenied("The 'task' query parameter is required.")
        
        
        self.company = get_object_or_404(Company, id=company_id)
        self.userStaff = get_object_or_404(User, id=user_id)
        self.branch = get_object_or_404(Branch, id=branch_id, company=self.company)
        self.staff = get_object_or_404(Staff, user=self.userStaff, company=self.company)
        self.task = get_object_or_404(Task, company=self.company, branch=self.branch, id=task_id)

        self.max_points_data = self.staff.get_max_reward_points_and_value()
        self.max_monthly_points = self.max_points_data.get("max_points", 0)

        #print(self.max_points_data)

    def allocate_points(self, staff, task):
        """
        Allocate points to a staff member for a completed task, pending approval.

        Args:
            staff (Staff): The staff member object.
            task (Task): The completed task object.

        Returns:
            dict: A dictionary with allocation details or error messages.
        """
        
        if task.status == "rewardGranted":
            return {"status": "failure", "reason": "Task reward has already been granted"}
        
        if task.status not in ["completed", "appeal"]:
            return {"status": "failure", "reason": "Task is not marked as completed or approved appeal."}
        
        #print(self.task.status)
        if self.task.status == "appeal" or self.task.status == "completed":
            if not self.is_approved_by_hierarchy(staff, task):
                return {"status": "failure", "reason": "Task is under appeal and has not been approved by the appropriate lead."}

        if not staff.reward:
            return {"status": "failure", "reason": "Staff is not eligible for rewards."}
        
        if not self.is_dataset_complete(task):
            return {"status": "failure", "reason": "Incomplete dataset. Ensure all required entries are filled."}

        if not self.has_video_evidence(task):
            return {"status": "failure", "reason": "Video evidence is required for this task."}
        
        self.points_per_task = self.calculate_points(task)
        #print(self.points_per_task['proportional_points'])
        #print(self.points_per_task['ownerLoss_points'])
        
        self.total_monthly_points = self.get_monthly_allocated_points()
        #print(f"Total Monthly Points : {total_monthly_points}")

        self.log_points()
        print(self.log_points())

        self.reward_granted()

        return {
            "status": "pending",
            "staff": self.staff.user,
            "pending_points": self.points_per_task,
            "total_points_this_month": self.total_monthly_points + self.points_per_task,
        }

    def is_approved_by_hierarchy(self, staff, task):
        #print(self.task.approved_by)
        approved_by = task.approved_by
        if not approved_by:
            return False

        # Dynamically fetch StaffMember model based on task's appName
        StaffMemberModel = apps.get_model(task.appName, 'StaffMember')
        staffLead = StaffMemberModel.objects.filter(user=self.userStaff, branch=self.branch, company=self.company, status='active').first()
        staffLeadsLead = StaffMemberModel.objects.filter(user=staffLead.leader, branch=self.branch, company=self.company, status='active').first() 

        # Check if the task is approved by the staff's lead or staff lead's lead
        if task.approved_by == staffLead.leader or task.approved_by == staffLeadsLead.leader:
            if staffLead.leader == self.request.user or staffLeadsLead.leader == self.request.user:
                return True
    
        return False
    

    def approve_points(self, staff, points, task):
        if task.status != "pending":
            return {"status": "failure", "reason": "Task is not in a pending state for approval."}

        tracker_entry = RewardsPointsTracker.objects.filter(user=staff.user, task=task, points_pending=points).first()
        if not tracker_entry:
            raise ValueError("No matching pending points entry found for approval.")

        tracker_entry.points_pending -= points
        tracker_entry.credit += points
        tracker_entry.credit_date = now()
        tracker_entry.save()

        task.status = "completed"
        task.approved_by = staff.user
        task.approved_date = now()
        task.save()

        return {
            "status": "success",
            "approved_points": points,
            "total_approved_points": tracker_entry.credit,
        }

    def has_video_evidence(self, task):
        required_count = task.dataQuantity
        completed_entries = task.completeDetails.count('[')
        count = 0
        result = False
        for entry in task.completeDetails.split('['):
            if count > required_count:
                break
            if 'appName' in entry and 'modelName' in entry and 'modelId' in entry:
                app_name = entry.split('appName = ')[1].split(',')[0].strip()
                model_name = entry.split('modelName = ')[1].split(',')[0].strip()
                model_id = entry.split('modelId = ')[1].split(',')[0].strip()
                activity = entry.split('activity = ')[1].split(',')[0].strip()
                filled_out = entry.split('filledOut = ')[1].split(']')[0].strip()
                #print(f"appName: {app_name}, modelName: {model_name}, modelId: {model_id}, activity: {activity}, filledOut: {filled_out}")
            
                MediaData = Media.objects.filter(company=self.company, branch=self.branch, model_name=model_name, app_name=app_name, model_id=model_id, status='active').first()
                if MediaData and MediaData.file:
                    #print(f"Media file found for {model_name} with ID {model_id}")
                    result = True
                    
            count += 1

        return result

    def is_dataset_complete(self, task):
        required_count = task.dataQuantity
        completed_entries = task.completeDetails.count('[')
        if completed_entries  >= required_count:
            return True
        return False

    def calculate_points(self, task):
        print("")
        print("**** Calculate Points ***************************************")
        print("")
        activityData = ActivityOwner.objects.filter(activity=task.activity, branch=self.branch, company=self.company, status='active', appName=task.appName).first()
        totalBranchActivityData = ActivityOwner.objects.filter(branch=self.branch, company=self.company, status='active', appName=task.appName)
        totalBranchActivity = sum(activity.importance_scale * activity.min_estimated_count for activity in totalBranchActivityData)
        #print(self.max_points_data['max_points'])
        
        if totalBranchActivity == 0:
            return 0
        proportional_points = (self.max_points_data['max_points'] / totalBranchActivity) * (activityData.importance_scale)
        print(f"Starting Proportional Points : {proportional_points}")
        ownerLoss_points = 0
        days_late = (self.task.completed_date - self.task.due_date).days
        #print(f"days_late : {days_late}")

        
        #print(f"self.task.assistant : {self.task.assistant}") 
        #print(f"self.task.completed_by : {self.task.completed_by}")

        
        if self.task.assigned_to == self.task.completed_by:
            if self.task.completed_date and self.task.due_date:
                grace_period = 1
                penalty_days = days_late - grace_period
                print(f"penalty_days : {penalty_days}")
                penalty = min((proportional_points * 10/100) * penalty_days, (proportional_points * 50/100))
                print(f"Penalty Point to be deducted from owner  : {penalty}")
                ownerLoss_points += penalty
                proportional_points -= penalty
                print(f"Owner Proportional Points: {proportional_points}, ownerLoss_points: {ownerLoss_points}")
                return {'proportional_points': proportional_points, 'ownerLoss_points':ownerLoss_points}
                
            
        if self.task.completed_by == self.task.assistant:
            ownerLoss_points += proportional_points+(proportional_points * 10/100)
            grace_period = 3
            penalty_days = days_late - grace_period
            print(f"penalty_days : {penalty_days}")
            
            if penalty_days <= 0:
                proportional_points += (proportional_points * 10/100)
                print(f"Assitant Proportional Points: {proportional_points}, ownerLoss_points: {ownerLoss_points}")
                return {'proportional_points': proportional_points, 'ownerLoss_points':ownerLoss_points}
            
            if penalty_days >= 1:
                penalty = min((proportional_points * 10/100) * penalty_days, (proportional_points * 50/100))
                proportional_points -= penalty
                print(f"proportional_points: {proportional_points}, ownerLoss_points: {ownerLoss_points}")
                return {'proportional_points': proportional_points, 'ownerLoss_points':ownerLoss_points}
        
        StaffMemberModel = apps.get_model(self.task.appName, 'StaffMember')
        staffMember = StaffMemberModel.objects.filter(
            user=self.task.completed_by, 
            company=self.company, 
            branch=self.branch, 
            status='active'
        ).exclude(user__in=[self.task.assigned_to, self.task.assistant]).first()
        if staffMember:
            proportional_points += (proportional_points * 50/100)
            ownerLoss_points += proportional_points
            print(f"Start proportional_points: {proportional_points}, Start ownerLoss_points: {ownerLoss_points}")
            if self.task.completed_date and self.task.due_date:
                grace_period = 4
                penalty_days = days_late - grace_period
                print(f"penalty_days : {penalty_days}")
                if penalty_days >= 1:
                    penalty = min((proportional_points * 10/100) * penalty_days, (proportional_points * 70/100))
                    proportional_points -= penalty
                    print(f"proportional_points: {proportional_points}, ownerLoss_points: {ownerLoss_points}")
                return {'proportional_points': proportional_points, 'ownerLoss_points':ownerLoss_points}
                
        
        #print(proportional_points, ownerLoss_points)
        ownerLoss_points += proportional_points
        proportional_points = 0
        return {'proportional_points': proportional_points, 'ownerLoss_points':ownerLoss_points}
    
    def get_monthly_allocated_points(self):
            print("************ Monthly Allocated Points ****************")
            current_month = now().month
            current_year = now().year

            monthly_points = RewardsPointsTracker.objects.filter(
                user=self.task.assigned_to,
                credit_date__month=current_month,
                credit_date__year=current_year
            ).exclude(transaction_type='pending').aggregate(
                credit_total=Sum('credit'),
                blocked_total=Sum('blocked')
            )

            monthCreditReceived = monthly_points['credit_total'] or 0
            print(f"Month Credit Received : {monthCreditReceived}")
            monthBlockedPoints = monthly_points['blocked_total'] or 0
            print(f"Month Blocked Credit : {monthBlockedPoints}")

            total_monthly_points = monthCreditReceived + monthBlockedPoints

            
            return total_monthly_points

    def log_points(self):

        print("************ Log Points ****************")

        if self.task.status == "rewardGranted":
            return {"status": "failure", "reason": "Task reward has been granted already."}

        points_to_allocate = self.points_per_task['proportional_points']
        #print(f"Points to Allocate : {points_to_allocate}")
        points_to_blocked = self.points_per_task['ownerLoss_points']
        #print(f"Points to points_to_blocked : {points_to_blocked}")


        #print(f"self.task.assigned_to : {self.task.completed_by}")

        if self.task.assigned_to == self.task.completed_by:

            if self.total_monthly_points + self.points_per_task['proportional_points']  > self.max_monthly_points:
                return {"status": "failure", "reason": "No points to allocate."}

            RewardsPointsTracker.objects.create(
                user=self.task.completed_by,
                company=self.task.company,
                branch=self.task.branch,
                task=self.task,
                credit= points_to_allocate,
                transaction_type='merit'
            )

            RewardsPointsTracker.objects.create(
                user=self.task.assigned_to,
                company=self.task.company,
                branch=self.task.branch,
                task=self.task,
                blocked=points_to_blocked,
                transaction_type='merit'
            )
        
        else:
            RewardsPointsTracker.objects.create(
                user=self.task.completed_by,
                company=self.task.company,
                branch=self.task.branch,
                task=self.task,
                credit= points_to_allocate,
                transaction_type='merit'
            )

            RewardsPointsTracker.objects.create(
                user=self.task.assigned_to,
                company=self.task.company,
                branch=self.task.branch,
                task=self.task,
                blocked=points_to_blocked,
                transaction_type='merit'
            )

    def reward_granted(self):
        print("************ Reward Granted ****************")
        self.task.status = "rewardGranted"
        self.task.save()
        return {"status": "success", "reason": "Reward points granted successfully."}
    

def extract_common_data(request, fields):
    """
    Extracts and validates common data from the request based on the provided fields.
    """
    data = {field: request.data.get(field) for field in fields}

    # Ensure all required fields are provided
    missing_fields = [field for field, value in data.items() if not value]
    if missing_fields:
        logging.warning(f"Missing fields: {missing_fields}")
        return Response(
            {"error": f"Missing required fields: {', '.join(missing_fields)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return data



def notify_manager(activity, message):
    """
    Send a notification to the manager of the activity owner.
    """
    manager = activity.manager
    if manager:
        # Implement your notification logic here, e.g., email or push notification
        send_mail(
            subject=f"Notification for Activity {activity.name}",
            message=message,
            from_email='your_email@example.com',
            recipient_list=[manager.email],
        )
