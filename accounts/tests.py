from unittest import mock

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
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))

    def test_successful_login_redirects_to_dashboard(self):
        # A new user's first stop after logging in should be the app
        # (dashboard), not the profile/settings page. Login is by email.
        response = self.client.post(
            reverse("accounts:login"), {"email": "alice@example.com", "password": "pass12345"}
        )
        self.assertRedirects(response, reverse("dashboard"))


class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")

    def test_login_is_throttled_after_too_many_attempts(self):
        for _ in range(10):
            self.client.post(reverse("accounts:login"), {"email": "alice@example.com", "password": "wrong"})

        response = self.client.post(
            reverse("accounts:login"), {"email": "alice@example.com", "password": "pass12345"}, follow=True
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("Too many attempts" in m for m in messages))


class RegistrationFormTests(TestCase):
    def test_registration_form_has_no_username_field(self):
        # Sign-up is email-only; username is an internal, auto-generated
        # detail (profile URL slug), never typed by the user.
        form = UserRegistrationForm()
        self.assertNotIn("username", form.fields)

    def test_registering_generates_a_unique_username_from_the_email(self):
        response = self.client.post(reverse("accounts:register"), {
            "first_name": "Alice",
            "last_name": "Popescu",
            "email": "alice@example.com",
            "currency": "RON",
            "password1": "S3cure-Pass!23",
            "password2": "S3cure-Pass!23",
        })
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(email="alice@example.com")
        self.assertEqual(user.username, "alice")

    def test_duplicate_email_local_part_gets_a_numeric_suffix(self):
        User.objects.create_user(username="alice", email="alice@other-domain.com", password="pass12345")

        response = self.client.post(reverse("accounts:register"), {
            "first_name": "Alice",
            "last_name": "Ionescu",
            "email": "alice@example.com",
            "currency": "RON",
            "password1": "S3cure-Pass!23",
            "password2": "S3cure-Pass!23",
        })
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(email="alice@example.com")
        self.assertEqual(user.username, "alice2")

    def test_cannot_register_with_an_email_already_in_use(self):
        User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")

        response = self.client.post(reverse("accounts:register"), {
            "first_name": "Alice",
            "last_name": "Din nou",
            "email": "alice@example.com",
            "currency": "RON",
            "password1": "S3cure-Pass!23",
            "password2": "S3cure-Pass!23",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email__iexact="alice@example.com").count(), 1)


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="oldpass123")

    def test_request_view_declines_when_email_sending_is_not_configured(self):
        # RESEND_API_KEY isn't set in this environment, so the request view
        # must not pretend to send anything.
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "alice@example.com"}, follow=True
        )
        self.assertRedirects(response, reverse("accounts:login"))
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("isn't set up yet" in m for m in messages))

    def test_reset_request_does_not_reveal_whether_the_email_exists(self):
        with mock.patch("accounts.views.EMAIL_ENABLED", True):
            known = self.client.post(reverse("accounts:password_reset"), {"email": "alice@example.com"}, follow=True)
            unknown = self.client.post(reverse("accounts:password_reset"), {"email": "nobody@example.com"}, follow=True)

        known_messages = [m.message for m in known.context["messages"]]
        unknown_messages = [m.message for m in unknown.context["messages"]]
        self.assertEqual(known_messages, unknown_messages)

    def test_valid_token_allows_setting_a_new_password(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        response = self.client.post(
            reverse("accounts:password_reset_confirm", kwargs={"uidb64": uid, "token": token}),
            {"new_password1": "Brand-New-Pass!23", "new_password2": "Brand-New-Pass!23"},
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Brand-New-Pass!23"))

    def test_invalid_token_is_rejected(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        # No follow=True: this checks password_reset_confirm_view's own
        # redirect target, not wherever accounts:password_reset itself
        # bounces to next (which depends on EMAIL_ENABLED).
        response = self.client.get(
            reverse("accounts:password_reset_confirm", kwargs={"uidb64": uid, "token": "bad-token"}),
        )
        self.assertRedirects(
            response, reverse("accounts:password_reset"), target_status_code=302
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("oldpass123"))


class ProfileImageDefaultTests(TestCase):
    def test_new_user_has_no_image_so_the_template_placeholder_actually_shows(self):
        # image used to default to "default/user.jpg", a path nothing ever
        # ships to the media store — that made `user.image` truthy and
        # broke the profile template's `{% if user.image %}` fallback,
        # rendering a broken <img> instead of the placeholder icon.
        user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.assertFalse(user.image)

    def test_profile_page_does_not_render_an_image_tag_without_an_upload(self):
        user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:profile", args=[user.username]))
        self.assertNotContains(response, "<img")


class EmailCaseInsensitiveUniquenessTests(TestCase):
    def test_cannot_create_two_accounts_differing_only_by_email_case(self):
        from django.db import IntegrityError

        User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(username="alice2", email="Alice@Example.com", password="pass12345")
