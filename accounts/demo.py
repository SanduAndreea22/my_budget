import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model, logout
from django.utils import timezone

DEMO_LIFETIME = timedelta(hours=24)


def create_demo_user():
    """A fresh, isolated account with example data. No password: it can only be entered via the demo button."""
    from budget.demo import create_demo_data

    User = get_user_model()
    token = secrets.token_hex(6)
    user = User(
        username=f"demo-{token}", email=f"demo-{token}@demo.invalid",
        first_name="Demo", currency="RON", is_demo=True,
    )
    user.set_unusable_password()
    user.save()
    create_demo_data(user)
    return user


def cleanup_old_demo_users(older_than=DEMO_LIFETIME):
    """Delete demo accounts created more than `older_than` ago. Never touches real accounts."""
    User = get_user_model()
    cutoff = timezone.now() - older_than
    deleted = 0
    for user in User.objects.filter(is_demo=True, date_joined__lt=cutoff):
        user.delete()
        deleted += 1
    return deleted


def end_demo_session(request):
    """Log the visitor out of their demo account and delete it (and its data)."""
    user = request.user
    logout(request)
    if getattr(user, "is_demo", False):
        user.delete()
