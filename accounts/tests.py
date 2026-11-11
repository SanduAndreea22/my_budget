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

    def test_login_page_has_no_reset_link_but_says_what_to_do(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertNotContains(response, "password-reset")
        self.assertContains(response, "There is no reset yet")

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


class DemoAccountTests(TestCase):
    def setUp(self):
        cache.clear()

    def _start(self):
        return self.client.post(reverse("accounts:demo"))

    def test_demo_start_creates_a_logged_in_demo_account_with_example_data(self):
        from budget.models import BudgetLimit, SavingsGoal, Transaction
        response = self._start()
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(is_demo=True)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.email.endswith("@demo.invalid"))
        self.assertGreater(Transaction.objects.filter(user=user).count(), 20)
        self.assertTrue(BudgetLimit.objects.filter(user=user).exists())
        self.assertEqual(SavingsGoal.objects.filter(user=user).count(), 3)
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, "Demo mode")
        self.assertContains(page, "is over budget")

    def test_demo_start_only_accepts_post(self):
        response = self.client.get(reverse("accounts:demo"))
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(is_demo=True).exists())

    def test_each_visitor_gets_a_separate_account(self):
        from budget.models import Transaction
        self._start()
        first = User.objects.get(is_demo=True)
        self.client.logout()
        self._start()
        self.assertEqual(User.objects.filter(is_demo=True).count(), 2)
        second = User.objects.filter(is_demo=True).exclude(pk=first.pk).get()
        self.assertFalse(Transaction.objects.filter(user=second, pk__in=Transaction.objects.filter(user=first).values("pk")).exists())

    def test_logging_out_deletes_the_demo_account_and_its_data(self):
        from budget.models import Transaction
        self._start()
        user = User.objects.get(is_demo=True)
        self.client.post(reverse("accounts:logout"))
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Transaction.objects.filter(user_id=user.pk).exists())

    def test_demo_visitor_can_register_and_the_demo_is_deleted(self):
        self._start()
        demo = User.objects.get(is_demo=True)
        response = self.client.post(reverse("accounts:register"), {
            "email": "real@example.com", "currency": "EUR",
            "password1": "S3cure-Pass!23", "password2": "S3cure-Pass!23",
        })
        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(User.objects.filter(pk=demo.pk).exists())
        real = User.objects.get(email="real@example.com")
        self.assertFalse(real.is_demo)
        self.assertNotContains(self.client.get(reverse("dashboard")), "Demo mode")

    def test_demo_visitor_can_open_the_login_page(self):
        self._start()
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(is_demo=True).exists())

    def test_profile_changes_are_blocked_in_the_demo(self):
        self._start()
        user = User.objects.get(is_demo=True)
        response = self.client.post(reverse("accounts:profile", args=[user.username]), {
            "first_name": "Hacker", "last_name": "", "email": "evil@example.com", "description": "", "currency": "USD",
        })
        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Demo")
        self.assertTrue(user.email.endswith("@demo.invalid"))
        self.assertContains(self.client.get(reverse("accounts:profile", args=[user.username])), "profile changes are turned off")

    def test_cleanup_removes_only_old_demo_accounts(self):
        from datetime import timedelta
        from django.utils import timezone
        from accounts.demo import cleanup_old_demo_users, create_demo_user
        real = User.objects.create_user(username="real", email="real@example.com", password="pass12345")
        User.objects.filter(pk=real.pk).update(date_joined=timezone.now() - timedelta(days=400))
        old, fresh = create_demo_user(), create_demo_user()
        User.objects.filter(pk=old.pk).update(date_joined=timezone.now() - timedelta(hours=30))
        self.assertEqual(cleanup_old_demo_users(), 1)
        self.assertFalse(User.objects.filter(pk=old.pk).exists())
        self.assertTrue(User.objects.filter(pk=fresh.pk).exists())
        self.assertTrue(User.objects.filter(pk=real.pk).exists())

    def test_starting_a_demo_clears_expired_ones(self):
        from datetime import timedelta
        from django.utils import timezone
        from accounts.demo import create_demo_user
        old = create_demo_user()
        User.objects.filter(pk=old.pk).update(date_joined=timezone.now() - timedelta(hours=48))
        self._start()
        self.assertFalse(User.objects.filter(pk=old.pk).exists())
        self.assertEqual(User.objects.filter(is_demo=True).count(), 1)

    def test_demo_start_is_rate_limited(self):
        for _ in range(20):
            self.client.post(reverse("accounts:demo"))
            self.client.logout()
        before = User.objects.filter(is_demo=True).count()
        response = self.client.post(reverse("accounts:demo"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.filter(is_demo=True).count(), before)

    def test_an_already_logged_in_real_user_is_not_replaced_by_a_demo(self):
        real = User.objects.create_user(username="real", email="real@example.com", password="pass12345")
        self.client.force_login(real)
        self._start()
        self.assertFalse(User.objects.filter(is_demo=True).exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), real.pk)

    def test_management_command_runs(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("cleanup_demo_users", stdout=out)
        self.assertIn("Deleted 0 demo account(s).", out.getvalue())


class DemoDataLooksRealTests(TestCase):
    def test_demo_amounts_are_not_all_round_numbers(self):
        from decimal import Decimal
        from accounts.demo import create_demo_user
        from budget.models import Transaction
        user = create_demo_user()
        amounts = list(Transaction.objects.filter(user=user).values_list("amount", flat=True))
        with_cents = [a for a in amounts if a != a.to_integral_value()]
        self.assertGreater(len(with_cents) / len(amounts), 0.5)

    def test_demo_keeps_one_near_limit_and_one_over_budget_story(self):
        from accounts.demo import create_demo_user
        user = create_demo_user()
        self.client.force_login(user)
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, "Housing is near its limit")
        self.assertContains(page, "Shopping is over budget")
        self.assertNotContains(page, "Food is near its limit")


class DeleteAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        from budget.starter import create_starter_data
        self.user = User.objects.create_user(username="sam", email="sam@example.com", password="Right-Pass-77")
        self.other = User.objects.create_user(username="kim", email="kim@example.com", password="Other-Pass-77")
        for u in (self.user, self.other):
            create_starter_data(u)

    def _make_data(self, user):
        from datetime import date
        from budget.models import BudgetLimit, Category, RecurringTransaction, SavingsGoal, Transaction, Wallet
        cat = Category.objects.get(user=user, name="Food"); wal = Wallet.objects.get(user=user, name="Cash")
        Transaction.objects.create(user=user, category=cat, wallet=wal, type="expense", amount=10, date=date.today())
        BudgetLimit.objects.create(user=user, category=cat, month=date.today().replace(day=1), limit=100)
        RecurringTransaction.objects.create(user=user, type="expense", amount=5, category=cat, wallet=wal, day_of_month=1, start_date=date.today())
        SavingsGoal.objects.create(user=user, name="Trip", target_amount=100)

    def test_requires_login(self):
        response = self.client.get(reverse("accounts:delete_account"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_wrong_password_deletes_nothing(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:delete_account"), {"password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nothing was deleted")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_correct_password_deletes_the_account_and_all_its_data_only(self):
        from budget.models import ActivityLog, BudgetLimit, Category, RecurringTransaction, SavingsGoal, Transaction, Wallet
        for u in (self.user, self.other):
            self._make_data(u)
        ActivityLog.objects.create(user=self.user, action="create", model_name="Transaction", object_repr="x")
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:delete_account"), {"password": "Right-Pass-77"}, follow=True)
        self.assertRedirects(response, reverse("home"))
        self.assertContains(response, "Your account and all its data were deleted.")
        uid = self.user.pk
        self.assertFalse(User.objects.filter(pk=uid).exists())
        for model in (Transaction, BudgetLimit, RecurringTransaction, SavingsGoal, Category, Wallet, ActivityLog):
            self.assertFalse(model.objects.filter(user_id=uid).exists(), model.__name__)
        # the other account is untouched
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(Transaction.objects.filter(user=self.other).exists())
        self.assertTrue(Category.objects.filter(user=self.other).exists())
        # and the visitor is logged out
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_the_uploaded_avatar_file_is_removed_too(self):
        import io, os, tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image
        buf = io.BytesIO(); Image.new("RGB", (8, 8), "teal").save(buf, "PNG")
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.user.image.save("me.png", SimpleUploadedFile("me.png", buf.getvalue(), "image/png"), save=True)
            path = self.user.image.path
            self.assertTrue(os.path.exists(path))
            self.client.force_login(self.user)
            self.client.post(reverse("accounts:delete_account"), {"password": "Right-Pass-77"})
            self.assertFalse(os.path.exists(path))

    def test_profile_offers_deletion_but_demo_accounts_do_not(self):
        from accounts.demo import create_demo_user
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("accounts:profile", args=[self.user.username])), "Delete account")
        demo = create_demo_user()
        self.client.force_login(demo)
        self.assertNotContains(self.client.get(reverse("accounts:profile", args=[demo.username])), "Delete account")
        response = self.client.post(reverse("accounts:delete_account"), {"password": "x"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(pk=demo.pk).exists())  # demo cleanup is handled elsewhere


class DemoGuideTests(TestCase):
    """The "Things to try" guide must be true to the demo data and tick off real actions only."""

    def setUp(self):
        cache.clear()
        from accounts.demo import create_demo_user
        from budget.models import Category, SavingsGoal, Wallet
        self.user = create_demo_user()
        self.client.force_login(self.user)
        self.cat = lambda n: Category.objects.get(user=self.user, name=n)
        self.wallet = Wallet.objects.get(user=self.user, name="Card")
        self.goal = SavingsGoal.objects.get(user=self.user, name="New laptop")

    def _tour(self):
        return self.client.get(reverse("dashboard")).context["demo_tour"]

    def test_guide_starts_at_zero_and_example_data_never_counts(self):
        tour = self._tour()
        self.assertEqual((tour["done_count"], tour["total"]), (0, 4))
        self.assertContains(self.client.get(reverse("dashboard")), "Things to try")
        self.assertContains(self.client.get(reverse("dashboard")), "0 of 4 done")

    def test_real_users_do_not_see_the_guide(self):
        real = User.objects.create_user(username="real", email="real@example.com", password="pass12345")
        self.client.force_login(real)
        page = self.client.get(reverse("dashboard"))
        self.assertNotIn("demo_tour", page.context)
        self.assertNotContains(page, "Things to try")

    def test_each_step_is_ticked_by_the_real_action(self):
        from datetime import date
        self.client.post(reverse("add_expense"), {"amount": "100", "date": date.today().isoformat(), "category": self.cat("Food").pk, "wallet": self.wallet.pk, "note": ""})
        self.assertEqual([s["done"] for s in self._tour()["steps"]], [True, False, False, False])
        self.client.post(reverse("budget_add"), {"category": self.cat("Health").pk, "month": date.today().strftime("%Y-%m"), "limit": "100"})
        self.assertEqual([s["done"] for s in self._tour()["steps"]], [True, True, False, False])
        remaining = self.goal.target_amount - self.goal.saved_amount
        self.client.post(reverse("savings_goal_add_funds", args=[self.goal.pk]), {"amount": str(remaining)})
        self.assertEqual([s["done"] for s in self._tour()["steps"]], [True, True, True, False])
        self.client.post(reverse("recurring_add"), {"type": "expense", "amount": "40", "category": self.cat("Bills").pk, "wallet": self.wallet.pk,
                                                     "day_of_month": "5", "start_date": date.today().isoformat(), "note": "", "is_active": "on"})
        tour = self._tour()
        self.assertEqual(tour["done_count"], 4)
        self.assertContains(self.client.get(reverse("dashboard")), "That is the tour.")

    def test_the_food_hint_is_true(self):
        from datetime import date
        self.assertNotContains(self.client.get(reverse("dashboard")), "Food is near its limit")
        self.client.post(reverse("add_expense"), {"amount": "100", "date": date.today().isoformat(), "category": self.cat("Food").pk, "wallet": self.wallet.pk, "note": ""})
        self.assertContains(self.client.get(reverse("dashboard")), "Food is near its limit")

    def test_the_goal_hint_names_the_exact_remaining_amount_and_it_celebrates(self):
        remaining = self.goal.target_amount - self.goal.saved_amount
        hint = [s for s in self._tour()["steps"] if s["key"] == "goal"][0]["hint"]
        self.assertIn(f"{remaining:,.0f}" if remaining == remaining.to_integral_value() else f"{remaining:,.2f}", hint)
        response = self.client.post(reverse("savings_goal_add_funds", args=[self.goal.pk]), {"amount": str(remaining)})
        self.assertIn("celebrate=", response["Location"])

    def test_health_has_no_limit_yet_so_its_hint_is_true(self):
        from budget.models import BudgetLimit
        self.assertFalse(BudgetLimit.objects.filter(user=self.user, category=self.cat("Health")).exists())

    def test_banner_links_to_the_guide(self):
        self.assertContains(self.client.get(reverse("budgets")), 'href="/app/#demo-tour"')


class SignInCopyTests(TestCase):
    """Copy fixes from the text audit: register and login."""

    def setUp(self):
        cache.clear()

    def test_register_page_promises_only_what_it_delivers(self):
        html = self.client.get(reverse("accounts:register")).content.decode()
        self.assertNotIn("Start controlling", html)
        self.assertIn("Just an email and a password.", html)
        self.assertIn("<title>Create account · MyBudget</title>", html)
        self.assertIn("Log in instead", html)
        self.assertNotIn("Already have an account?", html)
        self.assertNotIn("Enter a valid email address.", html)               # no help text duplicating the error
        self.assertNotIn("Enter the same password as before", html)
        self.assertIn("Confirm password", html)
        self.assertNotIn("private and visible only to you", html)

    def test_password_rules_use_one_style(self):
        html = self.client.get(reverse("accounts:register")).content.decode()
        for rule in ("Don&#x27;t use your name or email in your password.", "Use at least 8 characters.",
                     "Pick something less common than", "Include at least one letter, not only numbers."):
            self.assertIn(rule, html)
        for old in ("At least 8 characters.", "Avoid common passwords", "Don&#x27;t reuse"):
            self.assertNotIn(old, html)

    def test_currency_options_are_written_the_same_way(self):
        html = self.client.get(reverse("accounts:register")).content.decode()
        for label in ("RON · Romanian leu", "EUR · Euro", "USD · US dollar", "GBP · British pound"):
            self.assertIn(label, html)

    def test_empty_submission_says_what_is_missing(self):
        response = self.client.post(reverse("accounts:register"), {})
        html = response.content.decode()
        for msg in ("Enter your email address.", "Choose a password.", "Type the password again."):
            self.assertIn(msg, html)
        self.assertNotIn("This field is required.", html)

    def test_mismatched_passwords_use_the_apps_own_wording(self):
        response = self.client.post(reverse("accounts:register"), {"email": "a@example.com", "password1": "S3cure-Pass!23", "password2": "other"})
        self.assertContains(response, "The two passwords don&#x27;t match.")
        self.assertNotContains(response, "didn’t match")

    def test_duplicate_email_suggests_logging_in(self):
        User.objects.create_user(username="x", email="taken@example.com", password="pass12345")
        response = self.client.post(reverse("accounts:register"), {"email": "taken@example.com", "currency": "RON", "password1": "S3cure-Pass!23", "password2": "S3cure-Pass!23"})
        self.assertContains(response, "Try logging in instead.")

    def test_login_failure_shows_one_plain_message_not_two(self):
        response = self.client.post(reverse("accounts:login"), {"email": "nobody@example.com", "password": "wrong"})
        html = response.content.decode()
        self.assertEqual(html.count("That email and password don&#x27;t match."), 1)
        self.assertNotIn("Invalid credentials", html)
        self.assertNotIn("inactive account", html)

    def test_login_page_drops_the_presumptuous_line_and_the_placeholder_echo(self):
        html = self.client.get(reverse("accounts:login")).content.decode()
        self.assertNotIn("right where you left it", html)
        self.assertNotIn('placeholder="Password"', html)

    def test_login_page_tells_you_what_to_do_if_you_forgot_your_password(self):
        html = self.client.get(reverse("accounts:login")).content.decode()
        self.assertIn("Forgot your password?", html)
        self.assertIn('href="/contact"', html)

    def test_welcome_messages_never_show_a_technical_username(self):
        User.objects.create_user(username="copy.empty", email="copy.empty@example.com", password="Right-Pass-77")
        response = self.client.post(reverse("accounts:login"), {"email": "copy.empty@example.com", "password": "Right-Pass-77"}, follow=True)
        self.assertContains(response, "Welcome back!")
        self.assertNotContains(response, "copy.empty!")
        self.client.logout()
        User.objects.create_user(username="sam", email="sam@example.com", password="Right-Pass-77", first_name="Sam")
        response = self.client.post(reverse("accounts:login"), {"email": "sam@example.com", "password": "Right-Pass-77"}, follow=True)
        self.assertContains(response, "Welcome back, Sam!")

    def test_registration_welcome_without_a_first_name(self):
        response = self.client.post(reverse("accounts:register"), {"email": "new.person@example.com", "currency": "RON", "password1": "S3cure-Pass!23", "password2": "S3cure-Pass!23"}, follow=True)
        self.assertContains(response, "Welcome! Your account is ready.")
        self.assertNotContains(response, "Welcome, new.person")

    def test_logout_message_has_no_filler(self):
        user = User.objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertContains(response, "You are logged out.")
        self.assertNotContains(response, "successfully")


class DemoCopyAuditTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_banner_says_when_the_demo_is_deleted_and_toast_does_not_repeat_it(self):
        response = self.client.post(reverse("accounts:demo"), follow=True)
        html = response.content.decode()
        self.assertIn("Everything here is example data, so change whatever you like.", html)
        self.assertIn("It is deleted when you log out, or after about a day.", html)
        self.assertNotIn("when you leave", html)
        self.assertIn("Create account →", html.split('class="container demo-banner"')[1].split("</div>")[0])
        self.assertContains(response, "Welcome to the demo.")
        self.assertEqual(html.count("Everything here is example data"), 1)  # banner only; the toast no longer repeats it
        self.assertNotIn("You&#x27;re in the demo", html)

    def test_each_guide_step_has_its_own_button_label_and_no_slang(self):
        response = self.client.post(reverse("accounts:demo"), follow=True)
        html = response.content.decode()
        for label in ("Add expense →", "Set a budget →", "Open goals →", "Add recurring →"):
            self.assertIn(label, html)
        self.assertNotIn("Try it →", html)
        import re
        visible = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", "", html, flags=re.S))
        self.assertNotIn("donut", visible.lower())       # class/id names are fine; the words people read are not
        self.assertNotIn("(say 100", html)
        self.assertNotIn("log itself", html)
        self.assertNotIn("Export from Transactions", html)
        self.assertNotIn("“", html)                       # no curly quotes mixed with straight ones

    def test_a_ticked_step_offers_do_it_again(self):
        from datetime import date
        from budget.models import Category, Wallet
        self.client.post(reverse("accounts:demo"))
        user = User.objects.get(is_demo=True)
        self.client.post(reverse("add_expense"), {"amount": "5", "date": date.today().isoformat(),
                                                   "category": Category.objects.get(user=user, name="Food").pk,
                                                   "wallet": Wallet.objects.get(user=user, name="Card").pk, "note": ""})
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn("Do it again →", html)
        self.assertNotIn("Again →", html.replace("Do it again →", ""))

    def test_goal_hint_drops_needless_decimals(self):
        from accounts.demo import create_demo_user
        from budget.demo import tour_steps
        hint = [s for s in tour_steps(create_demo_user())["steps"] if s["key"] == "goal"][0]["hint"]
        self.assertIn("2,940 RON", hint)
        self.assertNotIn("2,940.00", hint)
