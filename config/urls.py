import os

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from accounts.decorators import ratelimit_post

# Same best-effort per-IP throttle used on login/register, applied to the
# admin login too — it's the highest-privilege entry point (full access to
# every user's data) and Django's own admin login has no throttling.
admin.site.login = ratelimit_post('admin_login', limit=10, period_seconds=300)(admin.site.login)

# Configurable so production can move it off the guessable "admin/" path
# (set ADMIN_URL, e.g. "admin-a1b2c3/", in the environment).
ADMIN_URL = os.getenv("ADMIN_URL") or "admin/"

urlpatterns = [
    path(ADMIN_URL, admin.site.urls),
    path("auth/", include("accounts.urls")),
    path("", include("pages.urls")),
    path("app/", include("budget.urls")),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
