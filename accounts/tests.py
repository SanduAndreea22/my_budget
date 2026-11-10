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

    def test_registering_creates_a_cash_wallet_and_starter_categories(self):
        from budget.models import Category, Wallet
        self.client.post(reverse("accounts:register"), {
            "first_name": "Alice",
            "email": "alice@example.com",
            "currency": "RON",
            "password1": "S3cure-Pass!23",
            "password2": "S3cure-Pass!23",
        })
        user = User.objects.get(email="alice@example.com")
        self.assertEqual(list(Wallet.objects.filter(user=user).values_list("name", flat=True)), ["Cash"])
        names = set(Category.objects.filter(user=user).values_list("name", flat=True))
        self.assertTrue({"Salary", "Food", "Housing", "Transport"} <= names)
        self.assertTrue(Category.objects.filter(user=user, type="income").exists())
        self.assertTrue(Category.objects.filter(user=user, type="expense").exists())

    def test_starter_data_is_not_shared_between_users(self):
        from budget.models import Category, Wallet
        from budget.starter import create_starter_data
        a = User.objects.create_user(username="a", email="a@example.com", password="pass12345")
        b = User.objects.create_user(username="b", email="b@example.com", password="pass12345")
        create_starter_data(a)
        create_starter_data(b)
        self.assertEqual(Category.objects.filter(user=a).count(), Category.objects.filter(user=b).count())
        self.assertFalse(Category.objects.filter(user=a, pk__in=Category.objects.filter(user=b).values("pk")).exists())
        self.assertEqual(Wallet.objects.filter(user=a).count(), 1)

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


class NoEmailFlowsTests(TestCase):
    """The app sends no email at all while it is in testing."""

    def test_password_reset_routes_are_gone(self):
        self.assertEqual(self.client.get("/auth/password-reset").status_code, 404)
        self.assertEqual(self.client.get("/auth/reset/abc/def").status_code, 404)

    def test_login_page_has_no_forgot_password_link(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertNotContains(response, "Forgot")

    def test_activation_route_is_gone(self):
        self.assertEqual(self.client.get("/auth/activate/abc/def").status_code, 404)



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


class UserDeletionTests(TestCase):
    def test_deleting_a_user_with_transactions_does_not_raise(self):
        # budget.Category/Wallet are PROTECTed from Transaction/BudgetLimit/
        # RecurringTransaction (so a user can't delete a category/wallet
        # still in use) — which used to also block deleting the user
        # itself, since Django's User -> Category CASCADE ran into those
        # same protected rows before they were cleared.
        from datetime import date

        from budget.models import BudgetLimit, Category, RecurringTransaction, Transaction, Wallet

        user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        category = Category.objects.create(user=user, name="Food")
        wallet = Wallet.objects.create(user=user, name="Cash")
        Transaction.objects.create(user=user, type="expense", amount=10, date=date(2026, 1, 1), category=category, wallet=wallet)
        BudgetLimit.objects.create(user=user, category=category, month=date(2026, 1, 1), limit=100)
        RecurringTransaction.objects.create(
            user=user, type="expense", amount=10, category=category, wallet=wallet,
            day_of_month=1, start_date=date(2026, 1, 1),
        )

        user.delete()

        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())
        self.assertFalse(Transaction.objects.exists())
