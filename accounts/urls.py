from django.urls import path
from . import views
app_name = 'accounts'

urlpatterns = [
    path("register", views.register_view, name="register"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("demo", views.demo_start_view, name="demo"),
    path("delete-account", views.delete_account_view, name="delete_account"),
    path("profile/<username>", views.profile_view, name="profile"),
    # Dacă folosești activare email
]
