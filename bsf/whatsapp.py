

from django.core.exceptions import ValidationError
import re
import json
import datetime
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
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
    
    #also need to apply has_permission funtion here
    
    # get task by task_id
    task = get_object_or_404(Task, id=task_id)

    modelId = extract_data(task.description, "model_id")
    activity = extract_data(task.description, "Activity")
    current_stage = extract_data(task.description, "Stage")

    model = get_object_or_404(PondUseStats, id=modelId)

    if current_stage == "Start":
        end_date = get_from_folder(processed_data, "end_date")

    elif current_stage == "End":
        _end_activity(task, processed_data)

    return True


def _end_activity(task, processed_data): 
    """
    End the current activity for the given task.
    """
    print("******** Handle the end of an activity. ********")

    # ✅ Check if required data is complete
    try:
        data_complete = checkIfDataComplete(task, processed_data)
        if not data_complete["status"]:
                    print(f"❌ Data is incomplete: {data_complete['message']}. Stopping processing.")
                    return False  # Stop processing if data is incomplete
        
        # Retrieve the farm dynamically based on the company and branch from the task
        farm = get_object_or_404(
            apps.get_model("bsf", "Farm"),
            company=task.company,
        )
        print(f"Farm: {farm}")

        batch = get_object_or_404(
            apps.get_model("bsf", "Batch"),
            farm=farm,
            company=task.company,
            batch_name=extract_data(task.description, "Batch")
        )
        print(f"Batch: {batch}")

        

        model_id = extract_data(task.description, "model_id")
        print(f"Model ID: {model_id}")
        dataToSaveIn = get_object_or_404(
            PondUseStats, 
            id=model_id,
            company=task.company, 
            farm=farm, 
            batch=batch, 
            status="ongoing"
        )
        print(f"Pond Use Stats: {dataToSaveIn}")

        try:
            with transaction.atomic():

                # Convert end_date to a datetime.date object
                end_date = get_from_folder(processed_data, "end_date")
                print(f"End date: {end_date}")
                if isinstance(end_date, str):
                    try:
                        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
                    except ValueError:
                        raise ValidationError(f"Invalid format for end_date: {end_date}. Expected 'YYYY-MM-DD'.")

                if not isinstance(end_date, datetime.date):
                    raise ValueError(f"Invalid harvest_date: {end_date}. Expected a date object.")
                dataToSaveIn.harvest_date = end_date

                try:
                    harvest_weight = get_from_folder(processed_data, "harvest_weight")
                    harvest_weight = Decimal(harvest_weight)
                    print(f"Harvest weight: {harvest_weight}")
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid harvest_weight: {harvest_weight}. Expected a float or Decimal.")
                dataToSaveIn.harvest_weight = harvest_weight

                dataToSaveIn.status = "completed"
                dataToSaveIn.save()
        
        except Exception as e:
            print(f"Transaction error: {str(e)}")

    except (ValueError, TypeError) as e:
        print(f"❌ Data validation failed: {e}")
        return False  # Stop processing if an error is encountered

    print(f"✅ Task {task.id} completed successfully with processed data: {processed_data}")
    return True  # Proceed with activity completion


def checkIfDataComplete(task, processed_data):
    """
    Checks if all required fields from task.description exist and are valid in processed_data.
    """
    try:
        # ✅ Load task description as JSON
        form_data = json.loads(task.description)
    except json.JSONDecodeError:
        print("❌ Error: Task description is not a valid JSON.")
        raise ValueError("❌ Task description is invalid. Data validation failed.")

    # ✅ Ensure 'fields' key exists in task description
    fields = form_data.get("fields", [])
    print(f"Fields in task description: {fields}")
    if not fields:
        print("❌ Error: 'fields' not found in task description.")
        raise ValueError("❌ Task description is missing the 'fields' key. Data validation failed.")

    required_fields = []
    missing_fields = []

    # ✅ Identify required fields
    for field in fields:
        if field.get("required", False):  # Only check required fields
            required_fields.append(field["name"])

    # ✅ Validate required fields in processed_data
    for field_name in required_fields:
        if field_name in processed_data:
            print(f"Checking field '{field_name}' for '{processed_data[field_name]}' in processed_data...")
        else:
            print(f"Field '{field_name}' is missing in processed_data.")
        if field_name not in processed_data or not processed_data[field_name]:  # Check if key is missing or empty
            missing_fields.append(field_name)

    if missing_fields:
        print(f"❌ Missing required fields: {', '.join(missing_fields)}")
        return {"status": False, "message": f"Missing required fields: {', '.join(missing_fields)}"}

    print("✅ All required fields are present and valid.")
    return {"status": True, "message": f"✅ All required fields are present and valid."}



from django.apps import apps

