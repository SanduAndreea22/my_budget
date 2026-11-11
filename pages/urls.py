from django.urls import path
from .views import about_view, contact_view, home_view, privacy_view, whats_new_view

urlpatterns = [
    path("", home_view, name="home"),
    path("privacy", privacy_view, name="privacy"),
    path("about", about_view, name="about"),
    path("contact", contact_view, name="contact"),
    path("whats-new", whats_new_view, name="whats_new"),
]
