from django.urls import path
from django.views.generic import RedirectView

from .views import contact_view, home_view, privacy_view, whats_new_view

urlpatterns = [
    path("", home_view, name="home"),
    path("privacy", privacy_view, name="privacy"),
    # The About page was removed; old links land on Contact.
    path("about", RedirectView.as_view(pattern_name="contact", permanent=True)),
    path("contact", contact_view, name="contact"),
    path("whats-new", whats_new_view, name="whats_new"),
]
