from django.urls import path
from . import views
app_name = 'accounts'

urlpatterns = [
    path("register", views.register_view, name="register"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("profile/<username>", views.profile_view, name="profile"),
    # Dacă folosești activare email
    path("activate/<uidb64>/<token>", views.activate, name="activate"),
    path("password-reset", views.password_reset_request_view, name="password_reset"),
    path("reset/<uidb64>/<token>", views.password_reset_confirm_view, name="password_reset_confirm"),
]
