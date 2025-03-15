
import json
import re
from datetime import datetime
from django.core.cache import cache
from django.db.models import Q
from rest_framework.response import Response
from twilio.rest import Client
from django.apps import apps
from decouple import config

from company.models import Task

from .functions import extract_task_id



class WhatsAppTaskHandler:
    """
    Handles WhatsApp task execution dynamically based on form schema.
    """

    def __init__(self, request):
        """
        Extract WhatsApp request data.
        """
        self.sender_phone = request.data.get("From", "").replace("whatsapp:", "").strip()
        self.message = request.data.get("Body", "").strip().lower()
        self.media_url = request.data.get("MediaUrl0")

        # ✅ Retrieve logged-in user
        self.user_id = cache.get(f"whatsapp_logged_in_{self.sender_phone}")

        if not self.user_id:
            self.send_message("❌ You are not logged in. Please log in first.")
            return
        
        # ✅ Step 2: Retrieve stored task ID for the logged-in user
        stored_task_id = cache.get(f"task_{self.user_id}_id")

        # ✅ Step 3: Extract Task ID from message if provided
        extracted_task_id = extract_task_id(self)

        # ✅ Step 4: Set Task ID correctly
        if extracted_task_id:
            self.task_id = extracted_task_id  # Use extracted task ID
            cache.set(f"task_{self.user_id}_id", self.task_id)  # Store for future reference
        elif stored_task_id:
            self.task_id = stored_task_id  # Use stored task ID if extraction fails
        else:
            self.task_id = None  # No valid task ID found

        print(f"🔍 Final Active Task ID: {self.task_id}")  # ✅ Debug print

        # ✅ Retrieve active task ID
        self.task_id = cache.get(f"task_{self.user_id}_id")

        # ✅ Retrieve task details
        self.task = Task.objects.filter(id=self.task_id).first()

        if not self.task:
            self.send_message("❌ Task not found. Please start with 'Start Task <TaskID>'.")
            return

        # ✅ Parse form schema from task description
        try:
            self.form_schema = json.loads(self.task.description)
        except json.JSONDecodeError:
            self.send_message("❌ Task form configuration is invalid.")
            return

    def process_task_step(self):
        """
        Handles step-by-step form filling dynamically.
        """

        current_step = cache.get(f"whatsapp_step_{self.user_id}_{self.task_id}", 0)  # Track current field index
        fields = self.form_schema.get("fields", [])

        if current_step >= len(fields):
            return self.submit_task()

        field = fields[current_step]  # Get the current field
        field_name = field["name"]
        field_type = field["type"]
        required = field.get("required", False)
        multiple = field.get("multiple", False)
        check_existence = field.get("checkIfExisit", None)

        # ✅ Process user input based on field type
        if field_type == "text":
            if not self.message:
                return self.send_message(f"❌ Please enter a valid {field['label']}.")

            if check_existence:
                if not self.validate_existence(field_name, check_existence):
                    return self.send_message(f"❌ {field['label']} does not exist. Please enter a valid name.")

            stored_values = cache.get(f"task_{self.user_id}_{self.task_id}_{field_name}", [])
            stored_values.append(self.message)
            cache.set(f"task_{self.user_id}_{self.task_id}_{field_name}", stored_values)

            if multiple:
                return self.send_message(f"✅ {field['label']} saved. Enter another or type 'done' to continue.")

        elif field_type == "dropdown":
            if self.message not in field["options"]:
                return self.send_message(f"❌ Invalid selection. Choose: {', '.join(field['options'])}.")

            cache.set(f"task_{self.user_id}_{self.task_id}_{field_name}", self.message)

        elif field_type == "media":
            if self.message.lower() == "skip":
                cache.set(f"task_{self.user_id}_{self.task_id}_{field_name}", [])
            elif self.media_url:
                stored_values = cache.get(f"task_{self.user_id}_{self.task_id}_{field_name}", [])
                stored_values.append(self.media_url)
                cache.set(f"task_{self.user_id}_{self.task_id}_{field_name}", stored_values)
                return self.send_message("✅ Image saved. Send another or type 'done' to continue.")

        # ✅ Move to next field
        cache.set(f"whatsapp_step_{self.user_id}_{self.task_id}", current_step + 1)
        return self.ask_next_step()

    def validate_existence(self, field_name, check_conditions):
        """
        Checks if a field exists in the database before allowing input.
        """
        model_name = check_conditions.get("model")
        app_name = check_conditions.get("appName")
        status = check_conditions.get("status")
        search_field = check_conditions.get("pondName", "").replace("*", self.message)

        Model = apps.get_model(app_name, model_name)

        # ✅ Query database
        return Model.objects.filter(**{search_field: self.message, "status": status}).exists()

    def ask_next_step(self):
        """
        Sends the next question to the user.
        """
        current_step = cache.get(f"whatsapp_step_{self.user_id}_{self.task_id}", 0)
        fields = self.form_schema.get("fields", [])

        if current_step >= len(fields):
            return self.submit_task()

        field = fields[current_step]
        return self.send_message(f"📋 {field['label']}:")

    def submit_task(self):
        """
        Submits the completed task form.
        """
        form_data = {}

        for field in self.form_schema.get("fields", []):
            field_name = field["name"]
            form_data[field_name] = cache.get(f"task_{self.user_id}_{self.task_id}_{field_name}", "")

        print(f"📤 Submitting Task Data: {form_data}")

        self.send_message("✅ Task submitted successfully! Sending for approval.")

        # ✅ Clear session cache
        cache.delete(f"whatsapp_step_{self.user_id}_{self.task_id}")
        cache.delete(f"task_{self.user_id}_id")

        return Response({"message": "Task successfully submitted"}, status=200)

    def send_message(self, message_body):
        """
        Sends a WhatsApp message to the user.
        """
        TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID")
        TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        client.messages.create(
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{self.sender_phone}",
            body=message_body
        )

        print(f"📤 Sent WhatsApp Message to {self.sender_phone}: {message_body}")
        return Response({"message": "WhatsApp message sent"}, status=200)
