from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from .forms import UserRegistrationForm

User = get_user_model()


class AuthenticatedRedirectTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")

    def test_authenticated_user_is_redirected_away_from_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:login"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_authenticated_user_is_redirected_away_from_register(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:register"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_anonymous_user_can_see_login_page(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_user_is_redirected_to_login_from_protected_page(self):
        # Regression test: LOGIN_URL used to be the unnamespaced "login",
        # which doesn't exist (the URL is namespaced "accounts:login"),
        # so @login_required crashed with NoReverseMatch instead of
        # redirecting anonymous users to the login page.
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('dashboard')}")

    def test_logout_redirects_to_login(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))

    def test_successful_login_redirects_to_dashboard(self):
        # A new user's first stop after logging in should be the app
        # (dashboard), not the profile/settings page.
        response = self.client.post(
            reverse("accounts:login"), {"username": "alice", "password": "pass12345"}
        )
        self.assertRedirects(response, reverse("dashboard"))


class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")

    def test_login_is_throttled_after_too_many_attempts(self):
        for _ in range(10):
            self.client.post(reverse("accounts:login"), {"username": "alice", "password": "wrong"})

        response = self.client.post(
            reverse("accounts:login"), {"username": "alice", "password": "pass12345"}, follow=True
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("Too many attempts" in m for m in messages))


class RegistrationFormTextTests(TestCase):
    def test_username_field_explains_its_relation_to_email_login(self):
        form = UserRegistrationForm()
        self.assertIn("log in with your email", form.fields["username"].help_text)

    def test_registration_page_shows_the_username_help_text(self):
        response = self.client.get(reverse("accounts:register"))
        self.assertContains(response, "you can also log in with your email instead")
