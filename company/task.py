from celery import shared_task
from .models import ActivityOwner, Task
from django.utils import timezone


@shared_task
def check_and_generate_tasks():
    now = timezone.now()
    activities = ActivityOwner.objects.filter(is_active=True, reoccurring=True)
    print(f"Checking for activities at {now}")

    for activity in activities:
        if activity.reoccurring_end is None or activity.reoccurring_end > now:
            # Generate new task

            # Create the next task in the workflow
            Task.objects.create(
                company=activity.company,
                branch=activity.branch,
                title=f"{activity.activity} - {activity.owner}",
                due_date=(activity.reoccurring_end or now) + timezone.timedelta(days=activity.interval_days),
                assigned_to=activity.owner if activity else None,
                assistant=activity.assistant if activity else None,
                appName=activity.appName,
                modelName=activity.modelName,
                activity=activity.activity,
                status="active",
            )


