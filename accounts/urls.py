from django.urls import path
from . import views
app_name = 'accounts'

urlpatterns = [
    path("register", views.register_view, name="register"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("demo", views.demo_start_view, name="demo"),
    path("profile/<username>", views.profile_view, name="profile"),
    # Dacă folosești activare email
]
