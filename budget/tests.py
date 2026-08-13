from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Transaction

User = get_user_model()


class TransactionSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        self.own_category = Category.objects.create(user=self.user, name="Food")
        self.foreign_category = Category.objects.create(user=self.other_user, name="Rent")
        self.client.force_login(self.user)

    def test_cannot_attach_transaction_to_another_users_category(self):
        response = self.client.post(reverse("add_expense"), {
            "amount": "50",
            "date": "2026-01-10",
            "category": self.foreign_category.id,
            "note": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_can_add_expense_with_own_category(self):
        response = self.client.post(reverse("add_expense"), {
            "amount": "50",
            "date": "2026-01-10",
            "category": self.own_category.id,
            "note": "Groceries",
        })
        self.assertRedirects(response, reverse("dashboard"))
        tx = Transaction.objects.get()
        self.assertEqual(tx.user, self.user)
        self.assertEqual(tx.category, self.own_category)
        self.assertEqual(tx.type, Transaction.EXPENSE)

    def test_rejects_non_numeric_amount(self):
        response = self.client.post(reverse("add_income"), {
            "amount": "not-a-number",
            "date": "2026-01-10",
            "category": self.own_category.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_rejects_negative_amount(self):
        response = self.client.post(reverse("add_income"), {
            "amount": "-10",
            "date": "2026-01-10",
            "category": self.own_category.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_rejects_invalid_date(self):
        response = self.client.post(reverse("add_income"), {
            "amount": "10",
            "date": "not-a-date",
            "category": self.own_category.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)


class CategoryFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.client.force_login(self.user)

    def test_duplicate_category_name_shows_error_instead_of_crashing(self):
        Category.objects.create(user=self.user, name="Food")
        response = self.client.post(reverse("category_add"), {"name": "Food", "icon": "", "color": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.filter(user=self.user).count(), 1)

    def test_blank_category_name_is_rejected(self):
        response = self.client.post(reverse("category_add"), {"name": "   ", "icon": "", "color": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.count(), 0)


class TransactionsPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.client.force_login(self.user)
        for i in range(60):
            Transaction.objects.create(
                user=self.user,
                type=Transaction.EXPENSE,
                amount=10,
                date=date(2026, 1, 1),
                category=self.category,
            )

    def test_list_is_paginated(self):
        response = self.client.get(reverse("transactions"))
        self.assertEqual(len(response.context["page_obj"]), 50)
        self.assertTrue(response.context["page_obj"].has_next())
