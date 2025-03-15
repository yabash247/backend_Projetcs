



import re
from django.core.cache import cache
def extract_task_id(self):
        
        task_id = None

        # ✅ Step 2: Retrieve stored task ID for the logged-in user
        stored_task_id = cache.get(f"task_{self.user_id}_id")
        
        """
        Extracts the task ID from a WhatsApp message.
        Also switches to a new task if the user specifies a different one.
        """
        match = re.search(r"task\s+(\d+)", self.message)
        print(f"🔍 Extracted Task ID: {match.group(1)}" if match else "❌ No Task ID found.")
        if match:
            task_id = int(match.group(1))
            self.activate_task(self, task_id)
            return task_id
        

        return None


def activate_task(self, task_id):
        """
        Activate a new task while ensuring previous tasks retain their progress.
        """
        cache.set(f"whatsapp_active_task_{self.sender_phone}", task_id)
        cache.setdefault(f"whatsapp_step_{self.sender_phone}_{task_id}", "start_task")

        return self.send_message(f"✅ Task {task_id} activated! Send 'Start Task {task_id}' to begin or continue.")