from django.core.cache import cache
from django.shortcuts import render, redirect

from accounts.demo import cleanup_old_demo_users

def home_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")  # /app/
    _cleanup_demo_users_occasionally()
    return render(request, "pages/home.html")


def privacy_view(request):
    return render(request, "pages/privacy.html")


def _cleanup_demo_users_occasionally():
    """Remove expired demo accounts at most once every 15 minutes (cheap, indexed query)."""
    if cache.add("demo-cleanup-ran", True, 15 * 60):
        cleanup_old_demo_users()
