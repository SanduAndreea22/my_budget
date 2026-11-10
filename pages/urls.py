from django.urls import path
from .views import home_view, privacy_view

urlpatterns = [
    path("", home_view, name="home"),
    path("privacy", privacy_view, name="privacy"),
]
