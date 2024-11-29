from django.contrib.auth import get_user_model

User = get_user_model()

def check_user_exists(user_id: int):
    try:
        user = User.objects.get(id=user_id)
        return True, user
    except User.DoesNotExist:
        return False, None
    


