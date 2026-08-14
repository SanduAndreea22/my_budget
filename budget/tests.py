import csv
import io
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .models import BudgetLimit, Category, Transaction

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

    def test_form_values_are_preserved_after_a_validation_error(self):
        response = self.client.post(reverse("add_expense"), {
            "amount": "-10",
            "date": "2026-01-10",
            "category": self.own_category.id,
            "note": "Coffee",
        })
        self.assertContains(response, 'value="-10"')
        self.assertContains(response, 'value="2026-01-10"')
        self.assertContains(response, 'value="Coffee"')
        self.assertContains(response, f'value="{self.own_category.id}" selected')


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

    def test_color_field_renders_as_a_color_picker(self):
        response = self.client.get(reverse("category_add"))
        self.assertContains(response, 'type="color"')

    def test_color_field_has_a_sensible_default_for_new_categories(self):
        response = self.client.get(reverse("category_add"))
        self.assertEqual(response.context["form"].initial.get("color"), "#6366f1")

    def test_can_create_category_with_a_picked_color(self):
        response = self.client.post(reverse("category_add"), {"name": "Fun", "icon": "", "color": "#ff00aa"})
        self.assertRedirects(response, reverse("categories"))
        self.assertEqual(Category.objects.get(name="Fun").color, "#ff00aa")

    def test_accepts_a_multi_codepoint_emoji_as_icon(self):
        # A "single" emoji like a family or a flag can be several Unicode
        # code points long — this used to trip the old max_length=10 limit
        # with a confusing "has at most 10 characters" error.
        family_emoji = "👨‍👩‍👧‍👦"
        response = self.client.post(reverse("category_add"), {"name": "Family", "icon": family_emoji, "color": ""})
        self.assertRedirects(response, reverse("categories"))
        self.assertEqual(Category.objects.get(name="Family").icon, family_emoji)

    def test_overly_long_icon_gets_a_friendly_error_message(self):
        response = self.client.post(reverse("category_add"), {"name": "Long", "icon": "x" * 40, "color": ""})
        self.assertContains(response, "try a single emoji instead")
        self.assertEqual(Category.objects.filter(name="Long").count(), 0)


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


class CompareViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.client.force_login(self.user)
        Transaction.objects.create(user=self.user, type=Transaction.INCOME, amount=1000, date=date(2025, 1, 15), category=self.category)
        Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=300, date=date(2025, 1, 20), category=self.category)
        Transaction.objects.create(user=self.user, type=Transaction.INCOME, amount=1200, date=date(2026, 2, 5), category=self.category)
        Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=400, date=date(2026, 2, 10), category=self.category)

    def test_defaults_to_most_recent_year(self):
        response = self.client.get(reverse("compare"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_year"], 2026)
        self.assertEqual(response.context["year_total_income"], 1200)
        self.assertEqual(response.context["year_total_expense"], 400)

    def test_can_select_a_specific_year(self):
        response = self.client.get(reverse("compare"), {"year": "2025"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_year"], 2025)
        self.assertEqual(response.context["year_total_income"], 1000)
        self.assertEqual(response.context["year_total_expense"], 300)

    def test_year_over_year_totals(self):
        response = self.client.get(reverse("compare"))
        year_rows = {r["year"]: r for r in response.context["year_rows"]}
        self.assertEqual(year_rows[2025]["income"], 1000)
        self.assertEqual(year_rows[2026]["income"], 1200)

    def test_invalid_year_param_does_not_crash(self):
        response = self.client.get(reverse("compare"), {"year": "not-a-year"})
        self.assertEqual(response.status_code, 200)

    def test_only_sees_own_transactions(self):
        other = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        other_category = Category.objects.create(user=other, name="Rent")
        Transaction.objects.create(user=other, type=Transaction.INCOME, amount=99999, date=date(2026, 3, 1), category=other_category)

        response = self.client.get(reverse("compare"), {"year": "2026"})
        self.assertEqual(response.context["year_total_income"], 1200)

    def test_shows_empty_state_when_no_data_for_selected_year(self):
        response = self.client.get(reverse("compare"), {"year": "2030"})
        self.assertContains(response, "No transactions in 2030 yet.")
        self.assertNotContains(response, 'id="compareChart"')

    def test_shows_chart_when_year_has_data(self):
        response = self.client.get(reverse("compare"), {"year": "2026"})
        self.assertContains(response, 'id="compareChart"')
        self.assertNotContains(response, "No transactions in 2026 yet.")


class ExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        other_category = Category.objects.create(user=self.other_user, name="Secret")
        self.client.force_login(self.user)
        Transaction.objects.create(user=self.user, type=Transaction.INCOME, amount=500, date=date(2026, 1, 10), category=self.category, note="Salary")
        Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=75, date=date(2026, 1, 12), category=self.category, note="Groceries")
        Transaction.objects.create(user=self.other_user, type=Transaction.INCOME, amount=9999, date=date(2026, 1, 10), category=other_category, note="Not mine")

    def test_csv_export_contains_only_own_rows(self):
        response = self.client.get(reverse("export_transactions_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0], ["Date", "Type", "Category", "Amount", "Currency", "Note"])
        notes = [r[5] for r in rows[1:]]
        self.assertIn("Salary", notes)
        self.assertIn("Groceries", notes)
        self.assertNotIn("Not mine", notes)

    def test_csv_export_respects_type_filter(self):
        response = self.client.get(reverse("export_transactions_csv"), {"type": "income"})
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        notes = [r[5] for r in rows[1:]]
        self.assertEqual(notes, ["Salary"])

    def test_xlsx_export_contains_only_own_rows(self):
        response = self.client.get(reverse("export_transactions_xlsx"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        notes = [row[5].value for row in ws.iter_rows(min_row=2)]
        self.assertIn("Salary", notes)
        self.assertIn("Groceries", notes)
        self.assertNotIn("Not mine", notes)

    def test_pdf_export_returns_pdf(self):
        response = self.client.get(reverse("export_transactions_pdf"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_export_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("export_transactions_csv"))
        self.assertEqual(response.status_code, 302)


class EmptyCategoriesStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.client.force_login(self.user)

    def test_add_income_shows_create_category_prompt_when_no_categories(self):
        response = self.client.get(reverse("add_income"))
        self.assertContains(response, "You don't have any categories yet")
        self.assertContains(response, reverse("category_add"))
        self.assertNotContains(response, "<select name=\"category\"")

    def test_add_expense_shows_create_category_prompt_when_no_categories(self):
        response = self.client.get(reverse("add_expense"))
        self.assertContains(response, "You don't have any categories yet")
        self.assertNotContains(response, "<select name=\"category\"")

    def test_add_income_shows_form_once_a_category_exists(self):
        Category.objects.create(user=self.user, name="Salary")
        response = self.client.get(reverse("add_income"))
        self.assertNotContains(response, "You don't have any categories yet")
        self.assertContains(response, "<select name=\"category\"")


class BudgetLimitFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.client.force_login(self.user)

    def test_month_field_renders_as_a_month_picker(self):
        response = self.client.get(reverse("budget_add"))
        self.assertContains(response, 'type="month"')

    def test_can_create_a_budget_limit_with_month_only_value(self):
        response = self.client.post(reverse("budget_add"), {
            "category": self.category.id,
            "month": "2026-03",
            "limit": "500",
        })
        self.assertRedirects(response, reverse("budgets"))
        b = BudgetLimit.objects.get()
        self.assertEqual(b.month, date(2026, 3, 1))
        self.assertEqual(b.user, self.user)

    def test_edit_page_shows_existing_month_in_picker_format(self):
        b = BudgetLimit.objects.create(user=self.user, category=self.category, month=date(2026, 5, 1), limit=300)
        response = self.client.get(reverse("budget_edit", args=[b.id]))
        self.assertContains(response, 'value="2026-05"')


class BudgetsViewNoLimitStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        Category.objects.create(user=self.user, name="Food")
        self.client.force_login(self.user)

    def test_shows_explicit_no_limit_message_instead_of_hiding_the_row(self):
        response = self.client.get(reverse("budgets"))
        self.assertContains(response, "No limit set for this category yet.")
