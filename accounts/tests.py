from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

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
