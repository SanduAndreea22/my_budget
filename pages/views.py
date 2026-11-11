from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import render, redirect

from accounts.decorators import ratelimit_post
from accounts.demo import cleanup_old_demo_users

from .forms import ContactForm
from .models import FeedbackMessage

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


def about_view(request):
    return render(request, "pages/about.html")


def whats_new_view(request):
    return render(request, "pages/whats_new.html")


@ratelimit_post("contact", limit=5, period_seconds=3600)
def contact_view(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            if not form.cleaned_data["website"]:  # honeypot empty = a person
                FeedbackMessage.objects.create(
                    name=form.cleaned_data["name"], email=form.cleaned_data["email"],
                    message=form.cleaned_data["message"],
                    user=request.user if request.user.is_authenticated and not request.user.is_demo else None,
                )
            messages.success(request, "Thanks, your message was sent. If you left an email, any reply will go there.")
            return redirect("contact")
    else:
        form = ContactForm()
    return render(request, "pages/contact.html", {"form": form})
