from django.db.models.signals import post_save
from django.dispatch import receiver
from bsf.models import Farm  # Import the Farm model from the `bsf` app
from company.models import Branch


@receiver(post_save, sender=Farm)
def sync_branch_with_farm(sender, instance, created, **kwargs):
    """
    Automatically create or update a Branch in the company app when a Farm is created or updated.
    """
    if created:
        # Create a new Branch when a Farm is created
        Branch.objects.create(
            company=instance.company,
            name=instance.name,
            branch_id=instance.id,  # Use Farm's ID as the branch_id
            status=instance.status,  # Sync the status with the farm
            appName="bsf",  # App name
            modelName="Farm",  # Model name
        )
    else:
        # Update the Branch status if the Farm is updated
        try:
            branch = Branch.objects.get(branch_id=instance.id)
            branch.status = instance.status  # Sync status with the farm
            branch.save()
        except Branch.DoesNotExist:
            pass  # If no branch exists, do nothing
