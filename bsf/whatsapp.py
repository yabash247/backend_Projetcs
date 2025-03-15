

import re
from django.shortcuts import get_object_or_404
from company.models import Task  
from users.models import User
from bsf.models import PondUseStats  

def extract_data(data, keyword):
        if isinstance(data, dict):
            data = str(data)
        match = re.search(rf'"{keyword}"\s*:\s*"(\w+)"', data)
        if not match:
            match = re.search(rf'"{keyword}"\s*:\s*(\d+)', data)  
        if match:
            value = (match.group(1))
            return value
        elif match is None:
            print(f"Keyword '{keyword}' not found in data")
        return None

def get_from_folder(data, key):
    value = data.get(key)
    if value is None:
        raise ValueError(f"Key '{key}' not found in data")
    print(f"Value for '{key}' extracted: {value}")
    return value

def PondUseStats_whatsapp(task_id, processed_data, user_id):

    # check if user is authenticated
    user = get_object_or_404(User, id=user_id)
    if not user.is_authenticated:
        raise PermissionError("User is not authenticated")
    
    # get task by task_id
    task = get_object_or_404(Task, id=task_id)

    modelId = extract_data(task.description, "model_id")
    activity = extract_data(task.description, "Activity")
    current_stage = extract_data(task.description, "Stage")

    model = get_object_or_404(PondUseStats, id=modelId)

    if current_stage == "Start":
        end_date = get_from_folder(processed_data, "end_date")

    elif current_stage == "End":
        set_date = get_from_folder(processed_data, "set_date")
        Start_Weight = get_from_folder(processed_data, "Start_Weight")
        media = get_from_folder(processed_data, "media")
        

    return True


def _end_activity(self, request):
    """
    End the current activity for the given task.
    """
    print("""********Handle the end of an activity.********""")

    
