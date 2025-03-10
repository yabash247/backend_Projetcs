from django.core.cache import cache
from django.contrib.auth import authenticate
from rest_framework.response import Response
from twilio.rest import Client
from decouple import config
from django.utils.timezone import now
import re
import requests
import time
import os
from django.conf import settings
from django.core.files.base import ContentFile
from users.models import User, UserProfile
from company.models import Task, Media

from twilio.twiml.messaging_response import MessagingResponse

class WhatsAppHelpHandler:
    """
    Handles WhatsApp help requests and validates user inputs.
    """

    HELP_TOPICS = {
        "login": "🔑 *Login*: Log in using your phone number or email/password.\nExample: *Login email@example.com password123*",
        "logout": "🚪 *Logout*: Log out of your current WhatsApp session.\nExample: *Logout*",
        "tasks": "📋 *Show Tasks*: View your assigned tasks.\nExample: *Show Tasks*",
        "starttask": "▶️ *Start Task*: Begin executing a task.\nExample: *Start Task 45*",
        "completetask": "✅ *Complete Task*: Mark a task as completed.\nExample: *Complete Task 45*",
        "help": "❓ *Help*: View available commands or details on a specific command.\nExample: *Help StartTask*",
        "status": "🔍 *Check Status*: View the status of your assigned tasks.\nExample: *Status*",
        "switchtask": "🔄 *Switch Task*: Temporarily switch between tasks.\nExample: *Switch to Task 12*",
        "canceltask": "❌ *Cancel Task*: Stop working on a task.\nExample: *Cancel Task*",
    }

    VALID_ACTIONS = ["login", "logout", "show tasks", "start task", "complete task", "help", "status", "switch task", "cancel task"]

    def __init__(self, sender_phone, message):
        self.sender_phone = sender_phone
        self.message = message.strip().lower()
        self.user_id = cache.get(f"whatsapp_logged_in_{sender_phone}")  # Ensure user is logged in

    def process_help_request(self):
        """
        Processes a help request and returns either the full command list or details of a specific command.
        """

        # ✅ Ensure User is Logged In
        if not self.user_id:
            return self.send_message("❌ You are not logged in. Please log in first.")

        # ✅ Check if a task is currently active (Prevent Help Interruptions)
        if cache.get(f"whatsapp_task_active_{self.user_id}"):
            return self.send_message("⚠️ You are currently completing a task. Finish your task first or type 'Cancel Task' to stop.")

        if self.message.startswith("help "):
            command = self.message.split(" ")[1]  # Extract command keyword

            if command in self.HELP_TOPICS:
                return self.send_message(self.HELP_TOPICS[command])

            return self.send_message("❌ Unknown command. Send 'Help' to view all available commands.")

        help_text = "🤖 *Available Commands:*\n\n"
        for cmd, desc in self.HELP_TOPICS.items():
            help_text += f"➡️ *{cmd.capitalize()}* - {desc.split(':')[0]}\n"

        help_text += "\n📌 *Send 'Help <command>' to get details on a specific command.*"
        return self.send_message(help_text)

    def validate_input(self):
        """
        Validates user input, ensuring it is either a help command, an action word, or part of an ongoing session.
        """
        active_session = cache.get(f"whatsapp_task_active_{self.user_id}")

        if active_session:
            return None  # Allow processing since user is in an active session

        if self.message.startswith("help") or any(self.message.startswith(action) for action in self.VALID_ACTIONS):
            return None  # Allow valid commands

        return self.send_message("❌ Invalid input. Send 'Help' to view available command(s).")

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


class WhatsAppLoginHandler:
    """
    Handles WhatsApp authentication and login logic separately from WhatsAppTaskView.
    """

    def __init__(self, sender_phone, message):
        self.sender_phone = sender_phone
        self.message = message.strip().lower()

    def get_user(self):
        """Retrieve the user based on phone number (if linked)."""
        user_profile = UserProfile.objects.filter(phone=self.sender_phone).first()
        return user_profile.user if user_profile else None

    def check_existing_login(self):
        """Check if the user is logged in via a temporary session."""
        user_id = cache.get(f"whatsapp_temp_user_{self.sender_phone}")
        return User.objects.filter(id=user_id).first() if user_id else None

    def is_login_confirmed(self):
        """✅ Check if the user has already confirmed login to avoid repetitive questioning."""
        return cache.get(f"whatsapp_logged_in_{self.sender_phone}") is not None

    def start_login_process(self):
        """
        Begins login process if user is not logged in.
        """
        cache.set(f"whatsapp_login_state_{self.sender_phone}", True, timeout=600)  # ✅ Login process starts

    def welcome_and_confirm_login(self):
        """
        If the user is logged in, ask if they want to continue or switch accounts.
        If not logged in, request login.
        """

        logged_in_user = self.check_existing_login()

        if logged_in_user:
            return self.ask_continue_or_switch(logged_in_user)

        detected_user = self.get_user()
        if detected_user:
            return self.ask_continue_or_switch(detected_user)

        return self.send_message("🔑 No linked account found. Reply with 'Login email@example.com password123' to log in.")
    
    def ask_continue_or_switch(self, user):
        """
        Asks user if they want to continue as the logged-in user or switch accounts.
        """
        cache.set(f"whatsapp_pending_confirmation_{self.sender_phone}", user.id, timeout=(86400 // 12))
        cache.set(f"whatsapp_login_state_{self.sender_phone}", True, timeout=600)  # ✅ Keep login state active

        message_body = (
            f"👋 Welcome! You are logged in as *{user.username}*.\n\n"
            "Reply with:\n"
            f"1️⃣ Continue as *{user.username}*\n"
            "2️⃣ Log in with another account*\n"
            "3️⃣ Log out*\n"
        )
        return self.send_message(message_body)

    def handle_login_confirmation(self):
        """
        Handles the user's response to login confirmation.
        """
        pending_user_id = cache.get(f"whatsapp_pending_confirmation_{self.sender_phone}")

        if not pending_user_id:
            #return self.send_message("❌ No pending login confirmation. Please start login by typing 'login'.")
             return None  # ✅ Instead of sending an error, return None if no login is pending

        if self.message.strip() == "1":  # ✅ Continue as detected user
            cache.set(f"whatsapp_logged_in_{self.sender_phone}", pending_user_id, timeout=86400)
            cache.delete(f"whatsapp_pending_confirmation_{self.sender_phone}")  # ✅ Remove pending state
            cache.delete(f"whatsapp_login_state_{self.sender_phone}")  # ✅ Clear login state
            return self.send_message(f"✅ Continuing as *{User.objects.get(id=pending_user_id).username}*. Send 'Show Tasks' to proceed.")

        elif self.message.strip() == "2":  # ✅ Switch to another account
            cache.delete(f"whatsapp_pending_confirmation_{self.sender_phone}")
            cache.set(f"whatsapp_login_state_{self.sender_phone}", True, timeout=600)  # ✅ Keep login state active
            return self.send_message("🔑 Please log in with your email & password:\n\nSend: *Login your@email.com password123*")
        
        elif self.message.strip() == "3":  # ✅ Logout
            return self.logout_user()

        return self.send_message("❌ Invalid response. Reply with 1️⃣ to continue or 2️⃣ to log in with another account.")


    def process_manual_login(self):
        """
        Handles manual email/password login.
        """
        try:
            _, email, password = self.message.split(" ")
        except ValueError:
            return self.send_message("❌ Invalid format. Use: 'Login email@example.com password123'.")

        user = authenticate(username=email, password=password)
        if not user:
            return self.send_message("❌ Invalid credentials. Please try again.")

        cache.set(f"whatsapp_logged_in_{self.sender_phone}", user.id, timeout=86400)
        cache.delete(f"whatsapp_login_state_{self.sender_phone}")  # ✅ Remove login state
        self.delete_whatsapp_message()

        return self.send_message(f"✅ Successfully logged in as *{user.username}*. Send 'Show Tasks' to proceed.")

    def delete_whatsapp_message(self):
        """
        Inform user that credentials have been processed securely (cannot delete WhatsApp messages).
        """
        return self.send_message("🔒 Your login credentials have been processed securely.")

    
    
    def logout_user(self):
        """Logs the user out and requires re-login with a password."""
        user = self.get_user() or self.check_existing_login()

        if user:
            cache.delete(f"whatsapp_logged_in_{self.sender_phone}")
            cache.delete(f"whatsapp_temp_user_{self.sender_phone}")
            cache.delete(f"whatsapp_login_state_{self.sender_phone}")

            return self.send_message("✅ You have been logged out. To log back in, send your password:\n\n*Login yourpassword*")

        return self.send_message("❌ No active session found. Please log in using *Login email@example.com password123*.")

    def delete_whatsapp_message(self):
        """Inform user that credentials have been processed securely (cannot delete WhatsApp messages)."""
        return self.send_message("🔒 Your login credentials have been processed securely.")
    
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


class WhatsAppTaskHandler5:
    """
    Handles all WhatsApp task-related operations, including:
    - Showing available tasks
    - Allowing users to start tasks
    - Step-by-step task execution
    """

    def __init__(self, request):
        """
        Automatically extracts WhatsApp request data.
        """
        self.sender_phone = request.data.get("From", "").replace("whatsapp:", "").strip()
        self.message = request.data.get("Body", "").strip().lower()
        self.media_url = request.data.get("MediaUrl0")

    def process_task_request(self):
        """
        Determines the user's task request and routes accordingly.
        """
        # ✅ Check if user wants to see their tasks
        if self.message == "show tasks":
            return self.show_tasks()

        # ✅ Check if user wants to start a specific task
        task_id = self.extract_task_id(self.message)
        if task_id:
            return self.start_task(task_id)

        # ✅ Handle ongoing task steps
        return self.process_task_step()

    def show_tasks(self):
        """
        Fetches and displays the user's due tasks.
        """
        user_id = cache.get(f"whatsapp_logged_in_{self.sender_phone}")
        if not user_id:
            return self.send_message("❌ You are not logged in. Please log in first.")

        tasks = Task.objects.filter(assigned_to_id=user_id, status="active", due_date__gte=now()).order_by("due_date")

        if not tasks.exists():
            return self.send_message("✅ You have no pending tasks.")

        # ✅ Format task list for WhatsApp
        task_list_message = "📋 *Your Pending Tasks:*\n"
        for task in tasks:
            task_list_message += f"\n🔹 {task.id}: {task.title} (Due: {task.due_date.strftime('%Y-%m-%d')})"

        task_list_message += "\n\nReply with *Start Task <TaskID>* to begin."

        return self.send_message(task_list_message)

    def start_task(self, task_id):
        """
        Marks a task as 'in progress' and starts step-by-step form collection.
        """
        user_id = cache.get(f"whatsapp_logged_in_{self.sender_phone}")
        if not user_id:
            return self.send_message("❌ You are not logged in. Please log in first.")

        task = Task.objects.filter(id=task_id, assigned_to_id=user_id, status="active").first()
        if not task:
            return self.send_message("❌ Task not found or already started.")

        # ✅ Store task ID and set step to `end_date`
        cache.set(f"whatsapp_task_id_{self.sender_phone}", task_id, timeout=600)
        cache.set(f"whatsapp_step_{self.sender_phone}", "end_date")

        return self.ask_next_step("end_date")

    def process_task_step(self):
        """
        Handles step-by-step task execution dynamically.
        """
        task_id = cache.get(f"whatsapp_task_id_{self.sender_phone}")
        if not task_id:
            return self.send_message("❌ No active task found. Please start a task first.")

        current_step = cache.get(f"whatsapp_step_{self.sender_phone}", "end_date")

        # ✅ Step 1: Validate & Store End Date
        if current_step == "end_date":
            if not re.match(r"\d{4}-\d{2}-\d{2}", self.message):
                return self.send_message("❌ Invalid format! Enter the End Date (YYYY-MM-DD).")

            cache.set(f"task_{self.sender_phone}_end_date", self.message)
            cache.set(f"whatsapp_step_{self.sender_phone}", "harvest_weight")
            return self.ask_next_step("harvest_weight")

        # ✅ Step 2: Validate & Store Harvest Weight
        elif current_step == "harvest_weight":
            if not self.message.isdigit():
                return self.send_message("❌ Invalid input! Enter a numeric Harvest Weight (kg).")

            cache.set(f"task_{self.sender_phone}_harvest_weight", self.message)
            cache.set(f"whatsapp_step_{self.sender_phone}", "harvest_date")
            return self.ask_next_step("harvest_date")

        # ✅ Step 3: Validate & Store Harvest Date
        elif current_step == "harvest_date":
            if not re.match(r"\d{4}-\d{2}-\d{2}", self.message):
                return self.send_message("❌ Invalid format! Enter the Harvest Date (YYYY-MM-DD).")

            cache.set(f"task_{self.sender_phone}_harvest_date", self.message)
            cache.set(f"whatsapp_step_{self.sender_phone}", "media")
            return self.ask_next_step("media")

        # ✅ Step 4: Collect Media (Optional)
        elif current_step == "media":
            if self.message.lower() == "skip":
                cache.set(f"task_{self.sender_phone}_media", "None")
            elif self.media_url:
                cache.set(f"task_{self.sender_phone}_media", self.media_url)
            else:
                return self.send_message("📸 Upload a photo/video, or type 'SKIP' to continue.")

            # ✅ Final Step: Submit the Task
            return self.submit_task(task_id)

        return Response({"message": "Invalid step"}, status=400)

    def ask_next_step(self, step):
        """
        Sends the next question to the user based on the step.
        """
        questions = {
            "end_date": "📅 Please enter the *End Date* (YYYY-MM-DD):",
            "harvest_weight": "⚖️ Please enter the *Harvest Weight (kg)*:",
            "harvest_date": "📆 Please enter the *Harvest Date* (YYYY-MM-DD):",
            "media": "📸 Send a *photo or video* (or type SKIP to continue)."
        }

        return self.send_message(questions.get(step, "❌ Unknown step."))

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

    def submit_task(self, task_id):
        """
        Submits the collected task form data.
        """
        TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID")
        TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        end_date = cache.get(f"task_{self.sender_phone}_end_date", "")
        harvest_weight = cache.get(f"task_{self.sender_phone}_harvest_weight", "")
        harvest_date = cache.get(f"task_{self.sender_phone}_harvest_date", "")
        media = cache.get(f"task_{self.sender_phone}_media", "")

        form_data = {
            "end_date": end_date,
            "harvest_weight": harvest_weight,
            "harvest_date": harvest_date,
            "media": media
        }

        print(f"📤 Submitting Task Data: {form_data}")

        client.messages.create(
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{self.sender_phone}",
            body="✅ Task submission complete! Sending for approval."
        )

        return Response({"message": "Task submitted"}, status=200)


class WhatsAppTaskHandler:
    """
    Handles WhatsApp task interactions for starting, completing, and notifying users.
    """

    def __init__(self, request):
        """
        Extract WhatsApp request data and validate session continuity.
        """
        self.sender_phone = request.data.get("From", "").replace("whatsapp:", "").strip()
        self.message = request.data.get("Body", "").strip().lower()
        self.media_url = request.data.get("MediaUrl0")

        # ✅ Step 1: Retrieve logged-in user from cache
        self.user_id = cache.get(f"whatsapp_logged_in_{self.sender_phone}")

        if not self.user_id:
            self.send_message("❌ You are not logged in. Please log in first.")
            return

        # ✅ Step 2: Retrieve stored task ID for the logged-in user
        stored_task_id = cache.get(f"task_{self.user_id}_id")

        # ✅ Step 3: Extract Task ID from message if provided
        extracted_task_id = self.extract_task_id()

        # ✅ Step 4: Set Task ID correctly
        if extracted_task_id:
            self.task_id = extracted_task_id  # Use extracted task ID
            cache.set(f"task_{self.user_id}_id", self.task_id)  # Store for future reference
        elif stored_task_id:
            self.task_id = stored_task_id  # Use stored task ID if extraction fails
        else:
            self.task_id = None  # No valid task ID found

        print(f"🔍 Final Active Task ID: {self.task_id}")  # ✅ Debug print

        # ✅ Step 5: If no task ID is found, prompt user to start a task
        if not self.task_id:
            self.send_message("❌ No active task found. Please start with 'Start Task <TaskID>'.")
            return
        
        return

        # ✅ Proceed to process the task if everything is valid
        #self.process_whatsapp_task_step()


    def process_whatsapp_task_step(self):
        """
        Handles step-by-step WhatsApp task data collection dynamically.
        Ensures proper task step tracking and allows switching between tasks.
        """
        self.task_id = cache.get(f"task_{self.user_id}_id")

        if not self.task_id:
            return self.send_message("❌ No active task found. Please start with 'Start Task <TaskID>'.")
        
        # ✅ Set Task Lock (Prevents Interruption from Help Commands)
        cache.set(f"whatsapp_task_active_{self.user_id}", True, timeout=900)  # Task is active for 15 minutes

        
        # ✅ Handle "Switch to Task" Command
        if re.match(r"switch to task (\d+)", self.message, re.IGNORECASE):
            new_task_id = re.search(r"switch to task (\d+)", self.message, re.IGNORECASE).group(1)
            
            # ✅ Update active task ID in cache
            cache.set(f"task_{self.user_id}_id", new_task_id)
            cache.set(f"whatsapp_step_{self.user_id}_{new_task_id}", "start_task")  # Reset step
            
            return self.send_message(f"🔄 Switched to Task {new_task_id}. Send 'Start Task {new_task_id}' to continue.")


        # ✅ Retrieve the step associated with the current task
        current_step = cache.get(f"whatsapp_step_{self.user_id}_{self.task_id}", "start_task")
        

        print(f"🔄 Processing Step: {current_step} for Task {self.task_id}")

        if current_step == "start_task":
            cache.set(f"whatsapp_step_{self.user_id}_{self.task_id}", "end_date")
            return self.send_message("📅 Please enter the *End Date* (YYYY-MM-DD):")

        elif current_step == "end_date":
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", self.message.strip()):
                return self.send_message("❌ Invalid format! Please enter End Date in YYYY-MM-DD format.")

            cache.set(f"task_{self.user_id}_{self.task_id}_end_date", self.message)
            cache.set(f"whatsapp_step_{self.user_id}_{self.task_id}", "harvest_weight")
            return self.send_message("⚖️ Please enter the *Harvest Weight (kg)*:")

        elif current_step == "harvest_weight":
            if not self.message.isdigit():
                return self.send_message("❌ Invalid input! Please enter a numeric Harvest Weight (kg).")

            cache.set(f"task_{self.user_id}_{self.task_id}_harvest_weight", self.message)
            cache.set(f"whatsapp_step_{self.user_id}_{self.task_id}", "harvest_date")
            self.send_message("📆 Please enter the *Harvest Date* (YYYY-MM-DD):")
            return
              

        elif current_step == "harvest_date":
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", self.message.strip()):
                return self.send_message("❌ Invalid format! Please enter Harvest Date in YYYY-MM-DD format.")

            cache.set(f"task_{self.user_id}_{self.task_id}_harvest_date", self.message)
            cache.set(f"whatsapp_step_{self.user_id}_{self.task_id}", "media")
            self.send_message("📸 Send a *photo or video* (or type SKIP to continue).")
            return
              

        elif current_step == "media":
            if self.message.lower() == "skip":
                cache.set(f"task_{self.user_id}_{self.task_id}_media", "None")
            elif self.media_url:
                cache.set(f"task_{self.user_id}_{self.task_id}_media", self.media_url)
            else:
                return self.send_message("📸 Upload a photo/video, or type 'SKIP' to continue.")

            self.send_message("✅ Thanks! Submitting Task.....")  
            return self.submit_task()

        return self.send_message("❌ Invalid step.")
    

    def activate_task(self, task_id):
        """
        Activate a new task while ensuring previous tasks retain their progress.
        """
        cache.set(f"whatsapp_active_task_{self.sender_phone}", task_id)
        cache.setdefault(f"whatsapp_step_{self.sender_phone}_{task_id}", "start_task")

        return self.send_message(f"✅ Task {task_id} activated! Send 'Start Task {task_id}' to begin or continue.")

    def extract_task_id(self):
        """
        Extracts the task ID from a WhatsApp message.
        Also switches to a new task if the user specifies a different one.
        """
        match = re.search(r"task\s+(\d+)", self.message)
        print(f"🔍 Extracted Task ID: {match.group(1)}" if match else "❌ No Task ID found.")
        if match:
            task_id = int(match.group(1))
            self.activate_task(task_id)
            return task_id
        return None

    def get_user_by_phone(self):
        """
        Retrieves the user based on phone number.
        """
        user_profile = UserProfile.objects.filter(phone=self.sender_phone).first()
        return user_profile.user if user_profile else None

    def extract_task_id(self):
        """
        Extracts the task ID from a WhatsApp message.
        """
        match = re.search(r"(?:start|switch to) task\s+(\d+)", self.message)
        if match:
            task_id = int(match.group(1))
            print(f"🔄 Switching to Task {task_id}")
            cache.set(f"task_{self.user_id}_id", task_id)  # Update active task
            cache.set(f"whatsapp_step_{self.user_id}_{task_id}", "start_task")  # Ensure the new task starts fresh
            return task_id
        return None

    def ask_next_step(self, step):
        """
        Guides the user through the form one step at a time.
        """
        questions = {
            "end_date": "📅 Please enter the *End Date* (YYYY-MM-DD):",
            "harvest_weight": "⚖️ Please enter the *Harvest Weight (kg)*:",
            "harvest_date": "📆 Please enter the *Harvest Date* (YYYY-MM-DD):",
            "media": "📸 Send a *photo or video* (or type SKIP to continue)."
        }

        if step in questions:
            cache.set(f"whatsapp_task_step_{self.sender_phone}", step)
            return self.send_message(questions[step])

        return self.send_message("❌ Invalid step.")

    def send_message(self, message_body):
        """
        Sends a WhatsApp message to the user.
        """
        TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID")
        TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        TWILIO_PHONE_NUMBER = config("TWILIO_SANDBOX_PHONE_NUMBER")

        client.messages.create(
            from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
            to=f"whatsapp:{self.sender_phone}",
            body=message_body
        )

        print(f"📤 Sent WhatsApp Message to {self.sender_phone}: {message_body}")
        return Response({"message": "WhatsApp message sent"}, status=200)

    def submit_task(self):
        """
        Submits the collected task form data.
        """
        try:

            end_date = cache.get(f"task_{self.user_id}_{self.task_id}_end_date", "")
            harvest_weight = cache.get(f"task_{self.user_id}_{self.task_id}_harvest_weight", "")
            harvest_date = cache.get(f"task_{self.user_id}_{self.task_id}_harvest_date", "")
            media_url  = cache.get(f"task_{self.user_id}_{self.task_id}_media")
            
            print(f"📤 Submitting Task Data: {end_date}, {harvest_weight}, {harvest_date}, {media_url }")

            # ✅ Validate if all required fields are collected before submission
            if not end_date or not harvest_weight or not harvest_date:
                return self.send_message("❌ Some task fields are missing. Please complete all steps.")

            # ✅ Try downloading media
            media_file = None
            if media_url:
                print(f"📥 Downloading media from Twilio: {media_url}")
                media_file = download_media_from_twilio(media_url)

                if not media_file:
                    print("⚠️ No media file was saved. Proceeding without media.")

            task = Task.objects.get(id=self.task_id)
            if not task:
                return self.send_message("❌ Task not found. Please start a valid task.")
            
            userInstance = User.objects.get(id=self.user_id)
            # Save media if provided

            # ✅ Submit the task completion data

            media_obj = Media.objects.create( 
                    company=task.company,
                    branch=task.branch,
                    app_name=task.appName,
                    model_name=task.modelName,
                    file=media_file,  # Save downloaded file,
                    status="active",
                    model_id=task.id,
                    uploaded_by=userInstance,
                )
            
            print(f"📤 Media saved successfully: {media_obj.file.name}")

         

            # Create new task data in the model
            task.completed_by = userInstance
            task.status = "pending"
            task.save()

            print(f"📤 Task Submission Complete: {end_date}, {harvest_weight}, {harvest_date}, {media_url}")


             # ✅ Inform user that submission is in progress
            self.send_message("✅ Task submitted! Sending for approval.")

            # ✅ Clear session-related caches after task submission
            cache.delete(f"whatsapp_step_{self.user_id}_{self.task_id}")  # ✅ Clear step tracking
            cache.delete(f"task_{self.user_id}_id")  # ✅ Clear active task ID
            cache.delete(f"whatsapp_task_active_{self.user_id}")  # ✅ Clear active task flag

            return Response({"message": "Task successfully submitted"}, status=200)

        except Exception as e:
            print(f"❌ Error in submit_task: {e}")
            return Response({"error": "Task submission failed"}, status=500)

   
class WhatsAppUtils:


    """
    Utility functions for WhatsApp messaging.
    """
    @staticmethod
    def send_message(sender_phone, message_body):
        """
        Sends a WhatsApp message to the user.
        """
        TWILIO_ACCOUNT_SID = config("TWILIO_ACCOUNT_SID")
        TWILIO_AUTH_TOKEN = config("TWILIO_AUTH_TOKEN")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        TWILIO_PHONE_NUMBER = config("TWILIO_SANDBOX_PHONE_NUMBER")

        client.messages.create(
            from_=f"whatsapp:{TWILIO_PHONE_NUMBER}",
            to=f"whatsapp:{sender_phone}",
            body=message_body
        )

        print(f"📤 Sent WhatsApp Message to {sender_phone}: {message_body}")
        return Response({"message": "WhatsApp message sent"}, status=200)
    
from urllib.parse import urlparse
def download_media_from_twilio(media_url):
    """
    Downloads media from Twilio and saves it to local storage.
    """
    TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN

    try:
        # ✅ Extract filename from Twilio URL
        parsed_url = urlparse(media_url)
        file_name = os.path.basename(parsed_url.path)  # Extracts only 'MExxxxx'

        # ✅ Ensure file has a valid extension
        file_extension = file_name.split('.')[-1] if '.' in file_name else 'jpg'  # Default to jpg
        file_name = f"twilio_media_{int(time.time())}.{file_extension}"
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)

        # ✅ Download media from Twilio
        response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), stream=True)

        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            print(f"✅ Media downloaded and saved at {file_path}")
            return file_path  # Return saved file path

        else:
            print(f"❌ Failed to download media from Twilio: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ Error downloading media: {e}")
        return None





# Start task 55
# End Date 2022-12-25 

#fix issue of inptng data too early before getting prompot too

