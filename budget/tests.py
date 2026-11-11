import csv
import io
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from .models import ActivityLog, BudgetLimit, Category, RecurringTransaction, SavingsGoal, Transaction, Wallet
from .views import generate_due_recurring_transactions

User = get_user_model()


class TransactionSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        self.own_category = Category.objects.create(user=self.user, name="Food")
        self.foreign_category = Category.objects.create(user=self.other_user, name="Rent")
        self.own_wallet = Wallet.objects.create(user=self.user, name="Cash")
        self.foreign_wallet = Wallet.objects.create(user=self.other_user, name="Card")
        self.client.force_login(self.user)

    def test_cannot_attach_transaction_to_another_users_category(self):
        response = self.client.post(reverse("add_expense"), {
            "amount": "50",
            "date": "2026-01-10",
            "category": self.foreign_category.id,
            "wallet": self.own_wallet.id,
            "note": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_cannot_attach_transaction_to_another_users_wallet(self):
        response = self.client.post(reverse("add_expense"), {
            "amount": "50",
            "date": "2026-01-10",
            "category": self.own_category.id,
            "wallet": self.foreign_wallet.id,
            "note": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_can_add_expense_with_own_category(self):
        response = self.client.post(reverse("add_expense"), {
            "amount": "50",
            "date": "2026-01-10",
            "category": self.own_category.id,
            "wallet": self.own_wallet.id,
            "note": "Groceries",
        })
        self.assertRedirects(response, reverse("dashboard"))
        tx = Transaction.objects.get()
        self.assertEqual(tx.user, self.user)
        self.assertEqual(tx.category, self.own_category)
        self.assertEqual(tx.wallet, self.own_wallet)
        self.assertEqual(tx.type, Transaction.EXPENSE)

    def test_rejects_non_numeric_amount(self):
        response = self.client.post(reverse("add_income"), {
            "amount": "not-a-number",
            "date": "2026-01-10",
            "category": self.own_category.id,
            "wallet": self.own_wallet.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_rejects_negative_amount(self):
        response = self.client.post(reverse("add_income"), {
            "amount": "-10",
            "date": "2026-01-10",
            "category": self.own_category.id,
            "wallet": self.own_wallet.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_rejects_invalid_date(self):
        response = self.client.post(reverse("add_income"), {
            "amount": "10",
            "date": "not-a-date",
            "category": self.own_category.id,
            "wallet": self.own_wallet.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_form_values_are_preserved_after_a_validation_error(self):
        response = self.client.post(reverse("add_expense"), {
            "amount": "-10",
            "date": "2026-01-10",
            "category": self.own_category.id,
            "wallet": self.own_wallet.id,
            "note": "Coffee",
        })
        self.assertContains(response, 'value="-10"')
        self.assertContains(response, 'value="2026-01-10"')
        self.assertContains(response, 'value="Coffee"')
        self.assertContains(response, f'value="{self.own_category.id}" selected')
        self.assertContains(response, f'value="{self.own_wallet.id}" selected')


class CategoryFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.client.force_login(self.user)

    def test_duplicate_category_name_shows_error_instead_of_crashing(self):
        Category.objects.create(user=self.user, name="Food")
        response = self.client.post(reverse("category_add"), {"name": "Food", "type": "expense", "icon": "", "color": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.filter(user=self.user).count(), 1)

    def test_blank_category_name_is_rejected(self):
        response = self.client.post(reverse("category_add"), {"name": "   ", "type": "expense", "icon": "", "color": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.count(), 0)

    def test_color_field_renders_as_a_color_picker(self):
        response = self.client.get(reverse("category_add"))
        self.assertContains(response, 'type="color"')

    def test_rejects_a_color_that_is_not_a_hex_code(self):
        # The type="color" widget is just a UI hint — a raw POST (bypassing
        # the browser picker) could otherwise store arbitrary text that
        # ends up inside a style="background: ...;" attribute on every
        # page listing categories.
        response = self.client.post(reverse("category_add"), {
            "name": "Sketchy", "type": "expense", "icon": "", "color": "red; position:fixed",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Category.objects.filter(name="Sketchy").count(), 0)

    def test_color_field_has_a_sensible_default_for_new_categories(self):
        response = self.client.get(reverse("category_add"))
        self.assertEqual(response.context["form"].initial.get("color"), "#14b8a6")

    def test_can_create_category_with_a_picked_color(self):
        response = self.client.post(reverse("category_add"), {"name": "Fun", "type": "expense", "icon": "", "color": "#ff00aa"})
        self.assertRedirects(response, reverse("categories"))
        self.assertEqual(Category.objects.get(name="Fun").color, "#ff00aa")

    def test_accepts_a_multi_codepoint_emoji_as_icon(self):
        # A "single" emoji like a family or a flag can be several Unicode
        # code points long — this used to trip the old max_length=10 limit
        # with a confusing "has at most 10 characters" error.
        family_emoji = "👨‍👩‍👧‍👦"
        response = self.client.post(reverse("category_add"), {"name": "Family", "type": "expense", "icon": family_emoji, "color": ""})
        self.assertRedirects(response, reverse("categories"))
        self.assertEqual(Category.objects.get(name="Family").icon, family_emoji)

    def test_can_create_an_income_category(self):
        response = self.client.post(reverse("category_add"), {"name": "Bonus", "type": "income", "icon": "", "color": ""})
        self.assertRedirects(response, reverse("categories"))
        self.assertEqual(Category.objects.get(name="Bonus").type, Category.INCOME)

    def test_category_add_prefills_type_from_query_param(self):
        response = self.client.get(reverse("category_add"), {"type": "income"})
        self.assertEqual(response.context["form"].initial.get("type"), "income")

    def test_overly_long_icon_gets_a_friendly_error_message(self):
        response = self.client.post(reverse("category_add"), {"name": "Long", "type": "expense", "icon": "x" * 40, "color": ""})
        self.assertContains(response, "Use a single emoji.")
        self.assertEqual(Category.objects.filter(name="Long").count(), 0)


class CategoryDeleteProtectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.wallet = Wallet.objects.create(user=self.user, name="Cash")
        self.client.force_login(self.user)

    def test_can_delete_an_unused_category(self):
        response = self.client.post(reverse("category_delete", args=[self.category.id]))
        self.assertRedirects(response, reverse("categories"))
        self.assertFalse(Category.objects.filter(pk=self.category.pk).exists())

    def test_cannot_delete_a_category_with_transactions(self):
        Transaction.objects.create(
            user=self.user, type=Transaction.EXPENSE, amount=10, date=date(2026, 1, 1),
            category=self.category, wallet=self.wallet,
        )
        response = self.client.post(reverse("category_delete", args=[self.category.id]), follow=True)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("can't delete" in m for m in messages))

    def test_cannot_delete_a_category_with_a_budget_limit(self):
        BudgetLimit.objects.create(user=self.user, category=self.category, month=date(2026, 1, 1), limit=100)
        self.client.post(reverse("category_delete", args=[self.category.id]))
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_cannot_delete_a_category_with_a_recurring_transaction(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=10,
            category=self.category, wallet=self.wallet, day_of_month=1, start_date=date(2026, 1, 1),
        )
        self.client.post(reverse("category_delete", args=[self.category.id]))
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_confirm_page_shows_blocked_message_when_in_use(self):
        Transaction.objects.create(
            user=self.user, type=Transaction.EXPENSE, amount=10, date=date(2026, 1, 1),
            category=self.category, wallet=self.wallet,
        )
        response = self.client.get(reverse("category_delete", args=[self.category.id]))
        self.assertContains(response, "You can't delete this category")
        self.assertNotContains(response, "btn--danger")


class TransactionsPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.wallet = Wallet.objects.create(user=self.user, name="Cash")
        self.client.force_login(self.user)
        for i in range(60):
            Transaction.objects.create(
                user=self.user,
                type=Transaction.EXPENSE,
                amount=10,
                date=date(2026, 1, 1),
                category=self.category,
                wallet=self.wallet,
            )

    def test_list_is_paginated(self):
        response = self.client.get(reverse("transactions"))
        self.assertEqual(len(response.context["page_obj"]), 50)
        self.assertTrue(response.context["page_obj"].has_next())


class CompareViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.wallet = Wallet.objects.create(user=self.user, name="Cash")
        self.client.force_login(self.user)
        Transaction.objects.create(user=self.user, type=Transaction.INCOME, amount=1000, date=date(2025, 1, 15), category=self.category, wallet=self.wallet)
        Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=300, date=date(2025, 1, 20), category=self.category, wallet=self.wallet)
        Transaction.objects.create(user=self.user, type=Transaction.INCOME, amount=1200, date=date(2026, 2, 5), category=self.category, wallet=self.wallet)
        Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=400, date=date(2026, 2, 10), category=self.category, wallet=self.wallet)

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
        other_wallet = Wallet.objects.create(user=other, name="Card")
        Transaction.objects.create(user=other, type=Transaction.INCOME, amount=99999, date=date(2026, 3, 1), category=other_category, wallet=other_wallet)

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
        self.wallet = Wallet.objects.create(user=self.user, name="Cash")
        other_category = Category.objects.create(user=self.other_user, name="Secret")
        other_wallet = Wallet.objects.create(user=self.other_user, name="Card")
        self.client.force_login(self.user)
        Transaction.objects.create(user=self.user, type=Transaction.INCOME, amount=500, date=date(2026, 1, 10), category=self.category, wallet=self.wallet, note="Salary")
        Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=75, date=date(2026, 1, 12), category=self.category, wallet=self.wallet, note="Groceries")
        Transaction.objects.create(user=self.other_user, type=Transaction.INCOME, amount=9999, date=date(2026, 1, 10), category=other_category, wallet=other_wallet, note="Not mine")

    def test_csv_export_contains_only_own_rows(self):
        response = self.client.get(reverse("export_transactions_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0], ["Date", "Type", "Category", "Wallet", "Amount", "Currency", "Note"])
        notes = [r[6] for r in rows[1:]]
        self.assertIn("Salary", notes)
        self.assertIn("Groceries", notes)
        self.assertNotIn("Not mine", notes)

    def test_csv_export_respects_type_filter(self):
        response = self.client.get(reverse("export_transactions_csv"), {"type": "income"})
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        notes = [r[6] for r in rows[1:]]
        self.assertEqual(notes, ["Salary"])

    def test_csv_export_respects_wallet_filter(self):
        other_wallet = Wallet.objects.create(user=self.user, name="Savings")
        Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=20, date=date(2026, 1, 15), category=self.category, wallet=other_wallet, note="From savings")

        response = self.client.get(reverse("export_transactions_csv"), {"wallet": self.wallet.id})
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        notes = [r[6] for r in rows[1:]]
        self.assertIn("Salary", notes)
        self.assertNotIn("From savings", notes)

    def test_xlsx_export_contains_only_own_rows(self):
        response = self.client.get(reverse("export_transactions_xlsx"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        notes = [row[6].value for row in ws.iter_rows(min_row=2)]
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
        self.assertContains(response, "You don't have any income categories yet")
        self.assertContains(response, reverse("category_add"))
        self.assertNotContains(response, "<select name=\"category\"")

    def test_add_expense_shows_create_category_prompt_when_no_categories(self):
        response = self.client.get(reverse("add_expense"))
        self.assertContains(response, "You don't have any expense categories yet")
        self.assertNotContains(response, "<select name=\"category\"")

    def test_add_income_ignores_expense_only_categories(self):
        # A category that exists but is typed as an expense category
        # shouldn't count as "you have an income category" on Add Income.
        Category.objects.create(user=self.user, name="Food", type=Category.EXPENSE)
        response = self.client.get(reverse("add_income"))
        self.assertContains(response, "You don't have any income categories yet")

    def test_add_income_shows_wallet_prompt_once_a_category_exists_but_no_wallet(self):
        Category.objects.create(user=self.user, name="Salary", type=Category.INCOME)
        response = self.client.get(reverse("add_income"))
        self.assertNotContains(response, "You don't have any income categories yet")
        self.assertContains(response, "You don't have any wallets yet")
        self.assertContains(response, reverse("wallet_add"))
        self.assertNotContains(response, "<select name=\"category\"")

    def test_add_income_shows_form_once_a_category_and_wallet_exist(self):
        Category.objects.create(user=self.user, name="Salary", type=Category.INCOME)
        Wallet.objects.create(user=self.user, name="Cash")
        response = self.client.get(reverse("add_income"))
        self.assertNotContains(response, "You don't have any income categories yet")
        self.assertNotContains(response, "You don't have any wallets yet")
        self.assertContains(response, "<select name=\"category\"")
        self.assertContains(response, "<select name=\"wallet\"")


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

    def test_duplicate_limit_for_same_category_and_month_shows_error_instead_of_crashing(self):
        BudgetLimit.objects.create(user=self.user, category=self.category, month=date(2026, 3, 1), limit=500)
        response = self.client.post(reverse("budget_add"), {
            "category": self.category.id,
            "month": "2026-03",
            "limit": "700",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have a budget for this category and month")
        self.assertEqual(BudgetLimit.objects.filter(user=self.user, category=self.category, month=date(2026, 3, 1)).count(), 1)

    def test_editing_a_limit_to_clash_with_another_shows_error_instead_of_crashing(self):
        BudgetLimit.objects.create(user=self.user, category=self.category, month=date(2026, 3, 1), limit=500)
        other = BudgetLimit.objects.create(user=self.user, category=self.category, month=date(2026, 4, 1), limit=300)
        response = self.client.post(reverse("budget_edit", args=[other.id]), {
            "category": self.category.id,
            "month": "2026-03",
            "limit": "300",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already have a budget for this category and month")
        other.refresh_from_db()
        self.assertEqual(other.month, date(2026, 4, 1))


class BudgetsViewNoLimitStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        Category.objects.create(user=self.user, name="Food")
        self.client.force_login(self.user)

    def test_shows_explicit_no_limit_message_instead_of_hiding_the_row(self):
        response = self.client.get(reverse("budgets"))
        self.assertContains(response, "No limit set")
        self.assertContains(response, "Set budget")
        self.assertContains(response, "Food")

    def test_month_picker_renders_as_a_month_input(self):
        response = self.client.get(reverse("budgets"))
        self.assertContains(response, 'type="month"')

    def test_month_query_param_selects_that_month(self):
        response = self.client.get(reverse("budgets"), {"month": "2026-03"})
        self.assertEqual(response.context["month"], date(2026, 3, 1))
        self.assertContains(response, 'value="2026-03"')


class SavingsGoalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        self.client.force_login(self.user)

    def test_can_create_a_goal(self):
        response = self.client.post(reverse("savings_goal_add"), {
            "name": "Emergency fund",
            "target_amount": "1000",
            "target_date": "",
        })
        self.assertRedirects(response, reverse("savings_goals"))
        goal = SavingsGoal.objects.get()
        self.assertEqual(goal.user, self.user)
        self.assertEqual(goal.saved_amount, 0)

    def test_rejects_zero_or_negative_target(self):
        response = self.client.post(reverse("savings_goal_add"), {
            "name": "Bad goal", "target_amount": "0", "target_date": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SavingsGoal.objects.count(), 0)

    def test_add_funds_increases_saved_amount(self):
        goal = SavingsGoal.objects.create(user=self.user, name="Trip", target_amount=500)
        self.client.post(reverse("savings_goal_add_funds", args=[goal.id]), {"amount": "120"})
        goal.refresh_from_db()
        self.assertEqual(goal.saved_amount, 120)

        self.client.post(reverse("savings_goal_add_funds", args=[goal.id]), {"amount": "30"})
        goal.refresh_from_db()
        self.assertEqual(goal.saved_amount, 150)

    def test_add_funds_rejects_invalid_amount(self):
        goal = SavingsGoal.objects.create(user=self.user, name="Trip", target_amount=500)
        self.client.post(reverse("savings_goal_add_funds", args=[goal.id]), {"amount": "not-a-number"})
        goal.refresh_from_db()
        self.assertEqual(goal.saved_amount, 0)

    def test_progress_percentage_is_capped_at_100(self):
        goal = SavingsGoal.objects.create(user=self.user, name="Overfunded", target_amount=100, saved_amount=250)
        response = self.client.get(reverse("savings_goals"))
        rows = response.context["rows"]
        self.assertEqual(rows[0]["pct"], 100)
        self.assertTrue(rows[0]["is_complete"])

    def test_cannot_add_funds_to_another_users_goal(self):
        other_goal = SavingsGoal.objects.create(user=self.other_user, name="Not mine", target_amount=500)
        response = self.client.post(reverse("savings_goal_add_funds", args=[other_goal.id]), {"amount": "100"})
        self.assertEqual(response.status_code, 404)

    def test_cannot_delete_another_users_goal(self):
        other_goal = SavingsGoal.objects.create(user=self.other_user, name="Not mine", target_amount=500)
        response = self.client.post(reverse("savings_goal_delete", args=[other_goal.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(SavingsGoal.objects.filter(pk=other_goal.pk).exists())

    def test_delete_removes_the_goal(self):
        goal = SavingsGoal.objects.create(user=self.user, name="Trip", target_amount=500)
        response = self.client.post(reverse("savings_goal_delete", args=[goal.id]))
        self.assertRedirects(response, reverse("savings_goals"))
        self.assertFalse(SavingsGoal.objects.filter(pk=goal.pk).exists())

    def test_goals_list_shows_empty_state(self):
        response = self.client.get(reverse("savings_goals"))
        self.assertContains(response, "No savings goals yet")


class ActivityLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.wallet = Wallet.objects.create(user=self.user, name="Cash")
        self.client.force_login(self.user)

    def test_adding_a_transaction_is_logged(self):
        self.client.post(reverse("add_expense"), {
            "amount": "50", "date": "2026-01-10", "category": self.category.id, "wallet": self.wallet.id, "note": "Groceries",
        })
        entry = ActivityLog.objects.get()
        self.assertEqual(entry.user, self.user)
        self.assertEqual(entry.action, ActivityLog.CREATE)
        self.assertEqual(entry.model_name, "Transaction")
        self.assertIn("Food", entry.object_repr)

    def test_editing_a_transaction_is_logged(self):
        tx = Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=50, date="2026-01-10", category=self.category, wallet=self.wallet)
        self.client.post(reverse("transaction_edit", args=[tx.id]), {
            "type": "expense", "amount": "75", "date": "2026-01-10", "category": self.category.id, "wallet": self.wallet.id, "note": "",
        })
        entry = ActivityLog.objects.filter(action=ActivityLog.UPDATE).get()
        self.assertEqual(entry.model_name, "Transaction")

    def test_deleting_a_transaction_is_logged(self):
        tx = Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=50, date="2026-01-10", category=self.category, wallet=self.wallet)
        self.client.post(reverse("transaction_delete", args=[tx.id]))
        entry = ActivityLog.objects.filter(action=ActivityLog.DELETE).get()
        self.assertEqual(entry.model_name, "Transaction")

    def test_budget_limit_changes_are_logged(self):
        self.client.post(reverse("budget_add"), {
            "category": self.category.id, "month": "2026-01", "limit": "300",
        })
        entry = ActivityLog.objects.get()
        self.assertEqual(entry.model_name, "Budget Limit")
        self.assertEqual(entry.action, ActivityLog.CREATE)

    def test_activity_log_only_shows_own_entries(self):
        ActivityLog.objects.create(user=self.other_user, action=ActivityLog.CREATE, model_name="Transaction", object_repr="Not mine")
        ActivityLog.objects.create(user=self.user, action=ActivityLog.CREATE, model_name="Transaction", object_repr="Mine")
        response = self.client.get(reverse("activity_log"))
        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Not mine")

    def test_activity_log_page_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("activity_log"))
        self.assertEqual(response.status_code, 302)


class WalletTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.client.force_login(self.user)

    def test_can_create_a_wallet(self):
        response = self.client.post(reverse("wallet_add"), {"name": "Card", "icon": "💳"})
        self.assertRedirects(response, reverse("wallets"))
        wallet = Wallet.objects.get()
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.name, "Card")

    def test_duplicate_wallet_name_is_rejected(self):
        Wallet.objects.create(user=self.user, name="Cash")
        response = self.client.post(reverse("wallet_add"), {"name": "Cash", "icon": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Wallet.objects.filter(user=self.user).count(), 1)

    def test_blank_wallet_name_is_rejected(self):
        response = self.client.post(reverse("wallet_add"), {"name": "   ", "icon": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Wallet.objects.count(), 0)

    def test_wallets_list_shows_empty_state(self):
        response = self.client.get(reverse("wallets"))
        self.assertContains(response, "One wallet is where it starts")

    def test_wallet_balance_reflects_its_own_transactions_only(self):
        cash = Wallet.objects.create(user=self.user, name="Cash")
        card = Wallet.objects.create(user=self.user, name="Card")
        Transaction.objects.create(user=self.user, type=Transaction.INCOME, amount=1000, date="2026-01-01", category=self.category, wallet=cash)
        Transaction.objects.create(user=self.user, type=Transaction.EXPENSE, amount=200, date="2026-01-02", category=self.category, wallet=cash)
        Transaction.objects.create(user=self.user, type=Transaction.INCOME, amount=500, date="2026-01-03", category=self.category, wallet=card)

        response = self.client.get(reverse("wallets"))
        balances = {r["wallet"].id: r["balance"] for r in response.context["rows"]}
        self.assertEqual(balances[cash.id], 800)
        self.assertEqual(balances[card.id], 500)

    def test_only_own_wallets_appear_in_add_transaction_dropdown(self):
        # self.category ("Food", from setUp) defaults to an expense
        # category, so add_expense is the flow that actually reaches the
        # wallet dropdown here.
        own_wallet = Wallet.objects.create(user=self.user, name="Cash")
        Wallet.objects.create(user=self.other_user, name="Not mine")
        response = self.client.get(reverse("add_expense"))
        self.assertContains(response, "Cash")
        self.assertNotContains(response, "Not mine")


class WalletDeleteProtectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Food")
        self.wallet = Wallet.objects.create(user=self.user, name="Cash")
        self.client.force_login(self.user)

    def test_can_delete_an_unused_wallet(self):
        response = self.client.post(reverse("wallet_delete", args=[self.wallet.id]))
        self.assertRedirects(response, reverse("wallets"))
        self.assertFalse(Wallet.objects.filter(pk=self.wallet.pk).exists())

    def test_cannot_delete_a_wallet_with_transactions(self):
        Transaction.objects.create(
            user=self.user, type=Transaction.EXPENSE, amount=10, date=date(2026, 1, 1),
            category=self.category, wallet=self.wallet,
        )
        response = self.client.post(reverse("wallet_delete", args=[self.wallet.id]), follow=True)
        self.assertTrue(Wallet.objects.filter(pk=self.wallet.pk).exists())
        messages = [m.message for m in response.context["messages"]]
        self.assertTrue(any("can't delete" in m for m in messages))

    def test_cannot_delete_a_wallet_with_a_recurring_transaction(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=10,
            category=self.category, wallet=self.wallet, day_of_month=1, start_date=date(2026, 1, 1),
        )
        self.client.post(reverse("wallet_delete", args=[self.wallet.id]))
        self.assertTrue(Wallet.objects.filter(pk=self.wallet.pk).exists())


class RecurringTransactionGenerationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Subscriptions")
        self.wallet = Wallet.objects.create(user=self.user, name="Card")
        self.client.force_login(self.user)

    def test_generates_first_occurrence_in_start_month_when_day_already_passed_today(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=15,
            category=self.category, wallet=self.wallet,
            day_of_month=5, start_date=date(2026, 1, 1),
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 1, 10))
        tx = Transaction.objects.get()
        self.assertEqual(tx.date, date(2026, 1, 5))
        self.assertEqual(tx.amount, 15)
        self.assertEqual(tx.wallet, self.wallet)

    def test_does_not_generate_before_the_day_of_month_arrives(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=15,
            category=self.category, wallet=self.wallet,
            day_of_month=20, start_date=date(2026, 1, 1),
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 1, 10))
        self.assertEqual(Transaction.objects.count(), 0)

    def test_does_not_generate_before_start_date(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=15,
            category=self.category, wallet=self.wallet,
            day_of_month=1, start_date=date(2026, 6, 1),
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 3, 1))
        self.assertEqual(Transaction.objects.count(), 0)

    def test_catches_up_multiple_missed_months(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.INCOME, amount=2000,
            category=self.category, wallet=self.wallet,
            day_of_month=1, start_date=date(2026, 1, 1),
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 4, 15))
        dates = sorted(Transaction.objects.values_list("date", flat=True))
        self.assertEqual(dates, [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)])

    def test_does_not_duplicate_on_repeated_calls(self):
        r = RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=15,
            category=self.category, wallet=self.wallet,
            day_of_month=5, start_date=date(2026, 1, 1),
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 1, 10))
        generate_due_recurring_transactions(self.user, today=date(2026, 1, 10))
        generate_due_recurring_transactions(self.user, today=date(2026, 1, 31))
        self.assertEqual(Transaction.objects.count(), 1)
        r.refresh_from_db()
        self.assertEqual(r.last_generated, date(2026, 1, 5))

    def test_paused_recurring_transaction_does_not_generate(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=15,
            category=self.category, wallet=self.wallet,
            day_of_month=5, start_date=date(2026, 1, 1), is_active=False,
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 2, 1))
        self.assertEqual(Transaction.objects.count(), 0)

    def test_day_28_works_correctly_in_february(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=10,
            category=self.category, wallet=self.wallet,
            day_of_month=28, start_date=date(2026, 1, 1),
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 3, 1))
        dates = sorted(Transaction.objects.values_list("date", flat=True))
        self.assertEqual(dates, [date(2026, 1, 28), date(2026, 2, 28)])

    def test_generation_is_scoped_to_the_given_user(self):
        other = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        other_category = Category.objects.create(user=other, name="Rent")
        other_wallet = Wallet.objects.create(user=other, name="Card")
        RecurringTransaction.objects.create(
            user=other, type=RecurringTransaction.EXPENSE, amount=999,
            category=other_category, wallet=other_wallet,
            day_of_month=1, start_date=date(2026, 1, 1),
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 2, 1))
        self.assertEqual(Transaction.objects.count(), 0)

    def test_generated_transaction_is_logged(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=15,
            category=self.category, wallet=self.wallet,
            day_of_month=5, start_date=date(2026, 1, 1),
        )
        generate_due_recurring_transactions(self.user, today=date(2026, 1, 10))
        entry = ActivityLog.objects.get()
        self.assertEqual(entry.model_name, "Transaction")
        self.assertIn("recurring", entry.object_repr)

    def test_dashboard_visit_triggers_generation(self):
        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.INCOME, amount=3000,
            category=self.category, wallet=self.wallet,
            day_of_month=1, start_date=date(2020, 1, 1),
        )
        self.client.get(reverse("dashboard"))
        self.assertTrue(Transaction.objects.exists())


class RecurringTransactionCrudTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@example.com", password="pass12345")
        self.other_user = User.objects.create_user(username="bob", email="bob@example.com", password="pass12345")
        self.category = Category.objects.create(user=self.user, name="Subscriptions")
        self.wallet = Wallet.objects.create(user=self.user, name="Card")
        self.client.force_login(self.user)

    def test_add_prompts_for_category_when_none_exist(self):
        Category.objects.filter(user=self.user).delete()
        response = self.client.get(reverse("recurring_add"))
        self.assertContains(response, "You don't have any categories yet")

    def test_add_prompts_for_wallet_when_none_exist(self):
        Wallet.objects.filter(user=self.user).delete()
        response = self.client.get(reverse("recurring_add"))
        self.assertContains(response, "You don't have any wallets yet")

    def test_can_create_a_recurring_transaction(self):
        response = self.client.post(reverse("recurring_add"), {
            "type": "expense", "amount": "9.99", "category": self.category.id, "wallet": self.wallet.id,
            "day_of_month": "15", "start_date": "2026-01-01", "note": "Netflix", "is_active": "on",
        })
        self.assertRedirects(response, reverse("recurring_transactions"))
        r = RecurringTransaction.objects.get()
        self.assertEqual(r.user, self.user)
        self.assertEqual(r.day_of_month, 15)

    def test_rejects_zero_amount(self):
        response = self.client.post(reverse("recurring_add"), {
            "type": "expense", "amount": "0", "category": self.category.id, "wallet": self.wallet.id,
            "day_of_month": "15", "start_date": "2026-01-01",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RecurringTransaction.objects.count(), 0)

    def test_rejects_day_of_month_above_28(self):
        response = self.client.post(reverse("recurring_add"), {
            "type": "expense", "amount": "10", "category": self.category.id, "wallet": self.wallet.id,
            "day_of_month": "31", "start_date": "2026-01-01",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RecurringTransaction.objects.count(), 0)

    def test_cannot_edit_another_users_recurring_transaction(self):
        other_category = Category.objects.create(user=self.other_user, name="Rent")
        other_wallet = Wallet.objects.create(user=self.other_user, name="Card")
        other_r = RecurringTransaction.objects.create(
            user=self.other_user, type=RecurringTransaction.EXPENSE, amount=10,
            category=other_category, wallet=other_wallet, day_of_month=1, start_date=date(2026, 1, 1),
        )
        response = self.client.get(reverse("recurring_edit", args=[other_r.id]))
        self.assertEqual(response.status_code, 404)

    def test_cannot_delete_another_users_recurring_transaction(self):
        other_category = Category.objects.create(user=self.other_user, name="Rent")
        other_wallet = Wallet.objects.create(user=self.other_user, name="Card")
        other_r = RecurringTransaction.objects.create(
            user=self.other_user, type=RecurringTransaction.EXPENSE, amount=10,
            category=other_category, wallet=other_wallet, day_of_month=1, start_date=date(2026, 1, 1),
        )
        response = self.client.post(reverse("recurring_delete", args=[other_r.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(RecurringTransaction.objects.filter(pk=other_r.pk).exists())

    def test_delete_removes_it(self):
        r = RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.EXPENSE, amount=10,
            category=self.category, wallet=self.wallet, day_of_month=1, start_date=date(2026, 1, 1),
        )
        response = self.client.post(reverse("recurring_delete", args=[r.id]))
        self.assertRedirects(response, reverse("recurring_transactions"))
        self.assertFalse(RecurringTransaction.objects.filter(pk=r.pk).exists())

    def test_list_shows_empty_state(self):
        response = self.client.get(reverse("recurring_transactions"))
        self.assertContains(response, "No recurring transactions yet")

    def test_management_command_generates_for_all_users(self):
        from io import StringIO
        from django.core.management import call_command

        RecurringTransaction.objects.create(
            user=self.user, type=RecurringTransaction.INCOME, amount=3000,
            category=self.category, wallet=self.wallet, day_of_month=1, start_date=date(2020, 1, 1),
        )
        out = StringIO()
        call_command("generate_recurring_transactions", stdout=out)
        self.assertTrue(Transaction.objects.exists())
        self.assertIn("Checked recurring transactions", out.getvalue())


class StarterDataTests(TestCase):
    def test_create_starter_data_is_idempotent(self):
        from .starter import STARTER_CATEGORIES, create_starter_data
        user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        create_starter_data(user)
        create_starter_data(user)
        self.assertEqual(Wallet.objects.filter(user=user).count(), 1)
        self.assertEqual(Category.objects.filter(user=user).count(), len(STARTER_CATEGORIES))

    def test_create_starter_data_keeps_existing_category_untouched(self):
        from .starter import create_starter_data
        user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        Category.objects.create(user=user, name="Food", type="expense", icon="🥑", color="#112233")
        create_starter_data(user)
        food = Category.objects.get(user=user, name="Food")
        self.assertEqual((food.icon, food.color), ("🥑", "#112233"))

    def test_add_expense_form_prefills_today(self):
        from datetime import date
        from .starter import create_starter_data
        user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        create_starter_data(user)
        self.client.force_login(user)
        response = self.client.get(reverse("add_expense"))
        self.assertContains(response, f'value="{date.today().isoformat()}"')


class UsabilityPolishTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")

    def test_404_page_has_navigation_for_anonymous_visitors(self):
        response = self.client.get("/definitely-not-a-page")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "find that page", status_code=404)
        self.assertContains(response, "Go to homepage", status_code=404)
        self.assertContains(response, 'class="nav"', status_code=404)

    def test_404_page_for_logged_in_user_links_to_dashboard_and_shows_menu(self):
        self.client.force_login(self.user)
        response = self.client.get("/definitely-not-a-page")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Back to dashboard", status_code=404)
        self.assertContains(response, "subnav", status_code=404)

    def test_export_links_live_in_one_menu_and_keep_filters(self):
        from .starter import create_starter_data
        create_starter_data(self.user)
        cat = Category.objects.get(user=self.user, name="Food")
        wallet = Wallet.objects.get(user=self.user, name="Cash")
        Transaction.objects.create(user=self.user, category=cat, wallet=wallet, type="expense", amount=10, date=date.today())
        self.client.force_login(self.user)
        response = self.client.get(reverse("transactions"), {"type": "expense"})
        self.assertContains(response, 'class="menu menu--right"')
        for name in ("export_transactions_csv", "export_transactions_xlsx", "export_transactions_pdf"):
            self.assertContains(response, reverse(name) + "?type=expense")

    def test_category_and_wallet_forms_offer_quick_pickers(self):
        self.client.force_login(self.user)
        cat = self.client.get(reverse("category_add"))
        self.assertContains(cat, 'data-target="id_icon"')
        self.assertContains(cat, 'data-target="id_color"')
        wal = self.client.get(reverse("wallet_add"))
        self.assertContains(wal, 'data-target="id_icon"')
        self.assertNotContains(wal, 'data-target="id_color"')


class CurrencyEverywhereTests(TestCase):
    """The account currency must show on every amount, including history, labels and charts."""

    def setUp(self):
        from .starter import create_starter_data
        self.user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345", currency="EUR")
        create_starter_data(self.user)
        self.client.force_login(self.user)
        self.food = Category.objects.get(user=self.user, name="Food")
        self.cash = Wallet.objects.get(user=self.user, name="Cash")

    def _add_expense(self):
        return self.client.post(reverse("add_expense"), {
            "amount": "25", "date": date.today().isoformat(),
            "category": self.food.pk, "wallet": self.cash.pk, "note": "",
        })

    def test_activity_entries_follow_the_accounts_current_currency(self):
        self._add_expense()
        entry = ActivityLog.objects.get(user=self.user)
        self.assertIn("{cur}", entry.object_repr)
        self.assertNotIn("EUR", entry.object_repr)
        self.assertContains(self.client.get(reverse("activity_log")), "25.00 EUR")

        self.user.currency = "USD"
        self.user.save()
        page = self.client.get(reverse("activity_log"))
        self.assertContains(page, "25.00 USD")
        self.assertNotContains(page, "25.00 EUR")

    def test_old_activity_entries_are_converted_by_the_migration_pattern(self):
        import importlib
        mig = importlib.import_module("budget.migrations.0013_activitylog_currency_token")
        cases = {
            "Expense · Food · Cash · 25.00 RON": "Expense · Food · Cash · 25.00 {cur}",
            "Expense · Food · Cash · 25 EUR (recurring)": "Expense · Food · Cash · 25 {cur} (recurring)",
            "Expense · Rent · 1500.00 USD · day 5": "Expense · Rent · 1500.00 {cur} · day 5",
            "Food · Nov 2026 limit · 100.00 GBP": "Food · Nov 2026 limit · 100.00 {cur}",
            "Trip · target 900 RON": "Trip · target 900 {cur}",
        }
        for old, new in cases.items():
            self.assertEqual(mig.PATTERN.sub(r"\1 {cur}", old), new)
        # a number followed by a currency-like word in a NAME is left alone
        self.assertEqual(mig.PATTERN.sub(r"\1 {cur}", "Plan 5 RONDO · target 9 {cur}"), "Plan 5 RONDO · target 9 {cur}")

    def test_money_form_labels_show_the_currency(self):
        for name in ("budget_add", "savings_goal_add", "recurring_add"):
            self.assertContains(self.client.get(reverse(name)), "(EUR)", msg_prefix=name)

    def test_charts_get_the_currency_for_tooltips_and_axes(self):
        self.assertContains(self.client.get(reverse("charts")), 'const CURRENCY = "EUR"')
        self.assertContains(self.client.get(reverse("compare")), 'const CURRENCY = "EUR"')
        self._add_expense()
        self.assertContains(self.client.get(reverse("dashboard")), 'window.fmtMoney(c.parsed, "EUR")')


class MoneyFormatConsistencyTests(TestCase):
    def test_budgets_and_dashboard_alerts_format_amounts_the_same_way(self):
        from .starter import create_starter_data
        user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        create_starter_data(user)
        housing = Category.objects.get(user=user, name="Housing")
        wallet = Wallet.objects.get(user=user, name="Cash")
        today = date.today()
        BudgetLimit.objects.create(user=user, category=housing, month=today.replace(day=1), limit=1900)
        Transaction.objects.create(user=user, category=housing, wallet=wallet, type="expense", amount=1800, date=today)
        self.client.force_login(user)
        budgets = self.client.get(reverse("budgets"))
        self.assertContains(budgets, "1,800.00 RON")
        self.assertContains(budgets, "1,900.00 RON")
        self.assertContains(self.client.get(reverse("dashboard")), "1,800.00 of 1,900.00 RON spent")


class DashboardCopyAuditTests(TestCase):
    """Copy fixes from the text audit: dashboard, transactions and shared labels."""

    def setUp(self):
        from .starter import create_starter_data
        self.user = get_user_model().objects.create_user(username="copy.empty", email="copy.empty@example.com", password="pass12345")
        create_starter_data(self.user)
        self.client.force_login(self.user)
        self.cat = Category.objects.get(user=self.user, name="Food")
        self.wallet = Wallet.objects.get(user=self.user, name="Cash")

    def _expense(self, amount="58.70", when=None):
        return Transaction.objects.create(user=self.user, category=self.cat, wallet=self.wallet, type="expense",
                                          amount=amount, date=when or date(2026, 11, 9), note="Pharmacy")

    def test_greeting_never_shows_a_technical_username(self):
        page = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn("Hello 👋", page)
        self.assertNotIn("Hello, copy.empty", page)
        self.user.first_name = "Sam"; self.user.save()
        self.assertIn("Hello, Sam 👋", self.client.get(reverse("dashboard")).content.decode())

    def test_subtitle_describes_the_page_and_empty_state_is_plain(self):
        page = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn("Your totals, budget alerts and latest transactions.", page)
        self.assertNotIn("overview of your current budget", page)
        for gone in ("money story", "live picture", "logged this month"):
            self.assertNotIn(gone, page)
        self.assertIn("No spending this month yet. Your chart appears after your first expense.", page)
        self.assertIn("No transactions yet", page)

    def test_add_buttons_are_labelled_the_same_everywhere_with_a_real_minus(self):
        self._expense()
        for url in ("dashboard", "transactions"):
            page = self.client.get(reverse(url)).content.decode()
            self.assertIn("+ Add income", page, url)
            self.assertIn("− Add expense", page, url)
            for old in ("- Add expense", "- Expense", "+ Income<"):
                self.assertNotIn(old, page, f"{old!r} on {url}")
        for url in ("charts", "compare", "activity_log"):
            page = self.client.get(reverse(url)).content.decode()
            self.assertNotIn("- Add expense", page, url)

    def test_dates_use_one_format_with_no_leading_zero(self):
        tx = self._expense()
        for url in (reverse("dashboard"), reverse("transactions"), reverse("transaction_delete", args=[tx.pk])):
            self.assertIn("Nov 9, 2026", self.client.get(url).content.decode(), url)
            self.assertNotIn("Nov 09, 2026", self.client.get(url).content.decode(), url)
            self.assertNotIn("Nov. 9, 2026", self.client.get(url).content.decode(), url)

    def test_budget_delete_shows_the_month_in_words_not_iso(self):
        from .models import BudgetLimit
        b = BudgetLimit.objects.create(user=self.user, category=self.cat, month=date(2026, 11, 1), limit=200)
        page = self.client.get(reverse("budget_delete", args=[b.pk])).content.decode()
        self.assertIn("Month: Nov 2026", page)
        self.assertNotIn("2026-11", page)

    def test_amount_signs_have_no_space_on_any_list(self):
        self._expense()
        for url in ("dashboard", "transactions"):
            page = self.client.get(reverse(url)).content.decode()
            self.assertIn("-58.70 RON", page, url)
            self.assertNotIn("- 58.70 RON", page, url)

    def test_month_chart_total_has_the_same_precision_as_the_budgets_page(self):
        self._expense("3080.50", date.today())
        dash = self.client.get(reverse("dashboard")).content.decode()
        budgets = self.client.get(reverse("budgets")).content.decode()
        self.assertIn("3,080.50", dash)
        self.assertIn("3,080.50", budgets)

    def test_alerts_say_what_the_numbers_are(self):
        from .models import BudgetLimit
        BudgetLimit.objects.create(user=self.user, category=self.cat, month=date.today().replace(day=1), limit=100)
        Transaction.objects.create(user=self.user, category=self.cat, wallet=self.wallet, type="expense", amount=90, date=date.today())
        page = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn("Food is near its limit", page)
        self.assertNotIn("close to its limit", page)
        self.assertIn("90.00 of 100.00 RON spent · 90% this month", page)
        self.assertNotIn("90.00 / 100.00", page)
        self.assertIn("Open charts →", page)
        self.assertNotIn("Full charts", page)

    def test_live_preview_sign_has_no_space(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parent.parent / "static" / "js" / "animations.js").read_text()
        self.assertIn("card.dataset.sign + v.toLocaleString", js)
        self.assertNotIn('card.dataset.sign + " "', js)


class FormsAndListsCopyAuditTests(TestCase):
    """Copy fixes from the text audit: transactions, add income/expense and the shared forms."""

    def setUp(self):
        from .starter import create_starter_data
        self.user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        create_starter_data(self.user)
        self.client.force_login(self.user)
        self.food = Category.objects.get(user=self.user, name="Food")
        self.cash = Wallet.objects.get(user=self.user, name="Cash")

    def _page(self, name, *args):
        return self.client.get(reverse(name, args=args)).content.decode()

    def test_titles_use_sentence_case(self):
        import re
        tx = Transaction.objects.create(user=self.user, category=self.food, wallet=self.cash, type="expense", amount=5, date=date.today())
        pages = [self._page("add_income"), self._page("add_expense"), self._page("category_add"), self._page("wallet_add"),
                 self._page("budget_add"), self._page("savings_goal_add"), self._page("recurring_add"),
                 self._page("transaction_edit", tx.pk), self._page("transaction_delete", tx.pk), self._page("savings_goals")]
        for html in pages:
            title = re.search(r"<title>(.*?) · MyBudget</title>", html).group(1)
            h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.S).group(1).strip()
            for text in (title, h1):
                words = text.split()
                self.assertFalse(any(w[0].isupper() for w in words[1:] if w.isalpha()), f"Title Case: {text!r}")

    def test_transactions_page_describes_itself_and_the_export(self):
        Transaction.objects.create(user=self.user, category=self.food, wallet=self.cash, type="expense", amount=5, date=date.today())
        page = self._page("transactions")
        self.assertIn("All your income and expenses. Filter them, edit them or export them.", page)
        self.assertNotIn("Filter, edit and delete your transactions.", page)
        self.assertIn("Totals for all transactions that match your filters.", page)
        self.assertIn("Exports what matches your current filters.", page)
        self.assertEqual(page.count("Exports what matches your current filters."), 1)         # the note lives inside the menu only
        for gone in ("for spreadsheets and scripts", ".xlsx workbook"):
            self.assertNotIn(gone, page)
        self.assertIn("opens in any spreadsheet", page)

    def test_filters_say_how_many_are_applied_and_use_one_word_for_clearing(self):
        Transaction.objects.create(user=self.user, category=self.food, wallet=self.cash, type="expense", amount=5, date=date.today())
        plain = self._page("transactions")
        self.assertNotIn("applied", plain.split("Filters")[1][:200])
        filtered = self.client.get(reverse("transactions"), {"type": "expense", "wallet": self.cash.pk}).content.decode()
        self.assertIn("· 2 applied", filtered)
        self.assertNotIn("· active", filtered)
        for label in ("From date", "To date", "Clear filters"):
            self.assertIn(label, filtered)
        self.assertNotIn(">Reset<", filtered)

    def test_nothing_matches_message_and_previous_link(self):
        page = self.client.get(reverse("transactions"), {"type": "income", "from": "2020-01-01", "to": "2020-01-02"}).content.decode()
        self.assertIn("Nothing matches these filters", page)
        self.assertNotIn("No matches", page)
        for i in range(55):
            Transaction.objects.create(user=self.user, category=self.food, wallet=self.cash, type="expense", amount=1, date=date.today())
        page2 = self.client.get(reverse("transactions"), {"page": 2}).content.decode()
        self.assertIn("← Previous", page2)
        self.assertNotIn("← Prev<", page2)

    def test_add_forms_drop_the_obvious_tip_and_explain_the_preview(self):
        income, expense = self._page("add_income"), self._page("add_expense")
        self.assertNotIn("you can use decimals", income)
        self.assertIn("Preview (updates as you type)", income)
        self.assertIn("Type an amount", expense)
        self.assertNotIn("+ amount", income)
        self.assertNotIn("- amount", expense)
        self.assertIn("Add an expense instead", income)
        self.assertIn("Add income instead", expense)
        self.assertNotIn("Switch to", income + expense)
        self.assertIn("e.g. Groceries, rent, coffee", expense)


    def test_selects_say_what_to_do_instead_of_dashes(self):
        for name in ("budget_add", "recurring_add"):
            page = self._page(name)
            self.assertNotIn("---------", page, name)
            self.assertIn("Choose a category", page, name)
        recurring = self._page("recurring_add")
        self.assertIn("Choose a wallet", recurring)
        # the type select no longer starts with an empty choice
        type_select = recurring.split('name="type"')[1].split("</select>")[0]
        self.assertNotIn('value=""', type_select)

    def test_optional_fields_are_marked_the_same_way_everywhere(self):
        tx = Transaction.objects.create(user=self.user, category=self.food, wallet=self.cash, type="expense", amount=5, date=date.today())
        self.assertIn("Note (optional)", self._page("transaction_edit", tx.pk))
        self.assertIn("Note (optional)", self._page("recurring_add"))
        self.assertIn("Target date (optional)", self._page("savings_goal_add"))

    def test_budget_form_uses_budget_and_limit_consistently(self):
        page = self._page("budget_add")
        self.assertIn("Monthly limit (RON)", page)
        BudgetLimit.objects.create(user=self.user, category=self.food, month=date.today().replace(day=1), limit=100)
        response = self.client.post(reverse("budget_add"), {"category": self.food.pk, "month": date.today().strftime("%Y-%m"), "limit": "50"})
        self.assertContains(response, "You already have a budget for this category and month.")

    def test_recurring_form_has_plain_labels_and_help(self):
        page = self._page("recurring_add")
        self.assertIn("Active", page)
        self.assertNotIn("Is active", page)
        self.assertIn("Untick to pause it without deleting it.", page)
        self.assertIn("From 1 to 28, so it works in every month.", page)
        self.assertIn("Day of the month", page)
        self.assertIn("Starts on", page)

    def test_validation_messages_are_short_and_direct(self):
        response = self.client.post(reverse("add_expense"), {"amount": "0", "date": "", "category": "", "wallet": ""})
        html = response.content.decode()
        for msg in ("Enter an amount above 0.", "Choose a category.", "Choose a wallet.", "Enter a date."):
            self.assertIn(msg, html)
        for old in ("greater than zero", "Please choose one of your", "Please enter a valid"):
            self.assertNotIn(old, html)
        r2 = self.client.post(reverse("savings_goal_add"), {"name": "Trip", "target_amount": "0"})
        self.assertContains(r2, "Enter a target above 0.")
        r3 = self.client.post(reverse("category_add"), {"name": "", "type": "expense"})
        self.assertContains(r3, "Give the category a name.")
        r4 = self.client.post(reverse("wallet_add"), {"name": ""})
        self.assertContains(r4, "Give the wallet a name.")


class SectionsCopyAuditTests(TestCase):
    """Copy fixes from the text audit: categories, wallets, budgets, recurring, goals, charts, history, messages."""

    def setUp(self):
        from .starter import create_starter_data
        self.user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        create_starter_data(self.user)
        self.client.force_login(self.user)
        self.food = Category.objects.get(user=self.user, name="Food")
        self.cash = Wallet.objects.get(user=self.user, name="Cash")

    def html(self, name, *args):
        return self.client.get(reverse(name, args=args)).content.decode()

    # --- categories & wallets -------------------------------------------------
    def test_categories_and_wallets_say_what_they_are_for(self):
        self.assertIn("Group your income and spending, so your charts and budgets make sense.", self.html("categories"))
        self.assertIn("Keep your card, cash and savings apart, so each balance means something.", self.html("wallets"))
        self.assertNotIn("whatever accounts you use", self.html("wallet_add"))
        self.assertIn("Name it after where the money is", self.html("wallet_add"))

    def test_edit_forms_have_their_own_subtitle(self):
        self.assertIn("Change the name, type, emoji or color.", self.html("category_edit", self.food.pk))
        self.assertNotIn("Change the name, type, emoji or color.", self.html("category_add"))
        self.assertIn("Change the name or emoji.", self.html("wallet_edit", self.cash.pk))

    def test_emoji_and_color_fields_use_one_word_and_name_their_swatches(self):
        page = self.html("category_add")
        self.assertIn("Emoji (optional)", page)
        self.assertNotIn(">Icon<", page)
        self.assertIn('aria-label="Use teal"', page)
        self.assertNotIn("#14b8a6\"", page.split("aria-label")[1][:30])
        self.assertIn("click the swatch above for any color", page)
        self.assertNotIn("the box above", page)
        self.assertNotIn("type or paste", page)

    def test_blocked_delete_explains_how_to_unblock_and_links_to_the_transactions(self):
        Transaction.objects.create(user=self.user, category=self.food, wallet=self.cash, type="expense", amount=5, date=date.today())
        cat = self.html("category_delete", self.food.pk)
        self.assertIn("Move or delete those first", cat)
        self.assertIn(f'href="/app/transactions/?category={self.food.pk}"', cat)
        self.assertIn("Back to categories", cat)
        self.assertNotIn("Remove or reassign", cat)
        wal = self.html("wallet_delete", self.cash.pk)
        self.assertIn(f'href="/app/transactions/?wallet={self.cash.pk}"', wal)
        self.assertIn("Back to wallets", wal)

    def test_confirm_buttons_name_what_they_delete_and_numbers_are_formatted(self):
        from .models import RecurringTransaction
        budget = BudgetLimit.objects.create(user=self.user, category=self.food, month=date(2026, 11, 1), limit=1200)
        goal = SavingsGoal.objects.create(user=self.user, name="Trip", target_amount=4200, saved_amount=1260)
        rec = RecurringTransaction.objects.create(user=self.user, type="expense", amount=1500, category=self.food, wallet=self.cash, day_of_month=5, start_date=date.today())
        tx = Transaction.objects.create(user=self.user, category=self.food, wallet=self.cash, type="expense", amount=2500, date=date.today())
        pages = {"Delete budget": self.html("budget_delete", budget.pk), "Delete goal": self.html("savings_goal_delete", goal.pk),
                 "Delete recurring transaction": self.html("recurring_delete", rec.pk), "Delete transaction": self.html("transaction_delete", tx.pk)}
        for button, page in pages.items():
            self.assertIn(f">{button}</button>", page.replace("\n", "").replace("  ", ""), button)
            self.assertNotIn("Yes, delete", page)
            self.assertNotIn("This action cannot be undone", page)
            if "recurring" not in button:
                self.assertIn("This can't be undone.", page)
        self.assertIn("1,200.00 RON", pages["Delete budget"])
        self.assertIn("1,260.00 of 4,200.00 RON saved", pages["Delete goal"])
        self.assertIn("1,500.00 RON", pages["Delete recurring transaction"])
        self.assertIn("2,500.00 RON", pages["Delete transaction"])
        self.assertIn("Future transactions stop.", pages["Delete recurring transaction"])

    # --- budgets ------------------------------------------------------------------
    def test_budgets_explain_the_thresholds_and_do_not_compare_unlike_totals(self):
        housing = Category.objects.get(user=self.user, name="Housing")
        month = date.today().replace(day=1)
        BudgetLimit.objects.create(user=self.user, category=self.food, month=month, limit=100)
        Transaction.objects.create(user=self.user, category=self.food, wallet=self.cash, type="expense", amount=40, date=date.today())
        Transaction.objects.create(user=self.user, category=housing, wallet=self.cash, type="expense", amount=500, date=date.today())
        page = self.html("budgets")
        self.assertIn("Bars turn amber at 80% and red above 100%.", page)
        self.assertIn("40% used", page)
        self.assertIn("Total spent: <b", page)
        self.assertIn("540.00 RON", page)                                   # everything spent
        self.assertIn("In budgeted categories: <b", page)
        self.assertIn("40.00 RON</b> of <b", page)                           # only the category with a limit
        self.assertNotIn("Total limits", page)

    def test_budget_edit_has_its_own_subtitle(self):
        b = BudgetLimit.objects.create(user=self.user, category=self.food, month=date(2026, 11, 1), limit=100)
        self.assertIn("Change the category, month or limit.", self.html("budget_edit", b.pk))
        self.assertIn("Choose an expense category, a month and the most you want to spend on it.", self.html("budget_add"))

    # --- recurring ------------------------------------------------------------------
    def test_recurring_pages_use_one_name_and_plain_sentences(self):
        page = self.html("recurring_transactions")
        self.assertIn("Salary, rent and subscriptions that are added to your transactions every month.", page)
        self.assertIn("Add your salary, rent or a subscription once and it is added every month.", page)
        self.assertIn("+ Add recurring transaction", page)
        for gone in ("add themselves automatically", "from then on", "Add your first one", "it&#x27;ll be logged"):
            self.assertNotIn(gone, page)
        form = self.html("recurring_add")
        self.assertIn(">Add recurring transaction<", form.replace("\n", "").replace("  ", ""))
        self.assertIn("It is added to your transactions on the day you choose, every month.", form)
        self.assertNotIn("this day", form)

    # --- savings goals ---------------------------------------------------------------
    def test_goals_copy_and_labelled_add_funds_field(self):
        goal = SavingsGoal.objects.create(user=self.user, name="Trip", target_amount=100)
        page = self.html("savings_goals")
        self.assertIn("Set a target and see how close you are.", page)
        self.assertIn('placeholder="Amount in RON"', page)
        self.assertIn('aria-label="Amount to add to Trip"', page)
        self.assertNotIn("Add funds in RON (e.g. 100)", page)
        self.assertIn("Give it a name and the amount you want to save.", self.html("savings_goal_add"))
        self.assertIn("Change the name, target or date.", self.html("savings_goal_edit", goal.pk))

    # --- charts, yearly overview, change history ----------------------------------------------
    def test_charts_and_yearly_overview_say_what_they_show(self):
        charts = self.html("charts")
        self.assertIn("This month's spending by category, and income against expenses month by month.", charts)
        self.assertIn("Spending by category", charts)
        self.assertIn("Income vs expenses", charts)
        for gone in ("Visual overview", "Expenses by category", "Income vs Expense"):
            self.assertNotIn(gone, charts)
        overview = self.html("compare")
        self.assertIn("for the year you pick, month by month, and next to your other years.", overview)
        self.assertIn("Year by year", overview)
        self.assertNotIn("year-over-year", overview)
        self.assertNotIn("Yearly comparison", overview)
        self.assertIn("Nothing here yet. Your years appear once you add transactions.", overview)

    def test_change_history_uses_plain_names_and_lists_everything_it_records(self):
        self.client.post(reverse("budget_add"), {"category": self.food.pk, "month": date.today().strftime("%Y-%m"), "limit": "100"})
        self.client.post(reverse("savings_goal_add"), {"name": "Trip", "target_amount": "500"})
        page = self.html("activity_log")
        self.assertIn("transactions, budgets, savings goals and recurring transactions", page)
        self.assertNotIn("budget limit you", page)
        for name in ("Created</span>\n              budget", "Created</span>\n              savings goal"):
            self.assertIn(name, page)
        self.assertNotIn("Budget Limit", page)
        self.assertNotIn("Savings Goal", page)
        self.assertIn("· limit 100.00 RON", page)

    def test_change_history_empty_state_has_no_unrelated_button(self):
        page = self.html("activity_log")
        self.assertNotIn("Add expense", page)
        self.assertIn("is recorded here", page)

    # --- messages ----------------------------------------------------------------------------
    def test_confirmation_messages_use_one_tone_without_exclamation_marks(self):
        for url, data, msg in [("category_add", {"name": "Pets", "type": "expense"}, "Category created."),
                               ("wallet_add", {"name": "Savings"}, "Wallet created."),
                               ("savings_goal_add", {"name": "Bike", "target_amount": "300"}, "Savings goal created.")]:
            response = self.client.post(reverse(url), data, follow=True)
            self.assertContains(response, msg)
        self.assertNotContains(self.client.get(reverse("dashboard")), "created!")

    def test_reaching_a_goal_celebrates_without_repeating_itself(self):
        goal = SavingsGoal.objects.create(user=self.user, name="Bike", target_amount=100)
        response = self.client.post(reverse("savings_goal_add_funds", args=[goal.pk]), {"amount": "100"}, follow=True)
        self.assertContains(response, "You reached your target for &quot;Bike&quot;.")
        self.assertNotContains(response, "You hit")


class GoalsListCopyTests(TestCase):
    def test_goal_amounts_read_like_the_rest_of_the_app_and_no_stray_exclamation(self):
        user = get_user_model().objects.create_user(username="sam", email="sam@example.com", password="pass12345")
        SavingsGoal.objects.create(user=user, name="Trip", target_amount=4200, saved_amount=1260)
        SavingsGoal.objects.create(user=user, name="Bike", target_amount=100, saved_amount=100)
        self.client.force_login(user)
        page = self.client.get(reverse("savings_goals")).content.decode()
        self.assertIn("1,260.00 of 4,200.00 RON saved", page)
        self.assertNotIn("1,260.00 / 4,200.00", page)
        self.assertIn("Goal reached</span>", page)
        self.assertNotIn("Goal reached!", page)


class VisualHierarchyTests(TestCase):
    """Fixes from the UX/UI audit: what matters comes first on each page."""

    def setUp(self):
        from .starter import create_starter_data
        self.user = get_user_model().objects.create_user(username="vh", email="vh@example.com", password="pass12345")
        create_starter_data(self.user)
        self.client.force_login(self.user)

    def test_budgets_list_the_most_used_limit_first_and_unbudgeted_last(self):
        today = date.today().replace(day=1)
        food = Category.objects.get(user=self.user, name="Food")
        housing = Category.objects.get(user=self.user, name="Housing")
        wallet = Wallet.objects.get(user=self.user, name="Cash")
        BudgetLimit.objects.create(user=self.user, category=food, month=today, limit=1000)
        BudgetLimit.objects.create(user=self.user, category=housing, month=today, limit=100)
        Transaction.objects.create(user=self.user, category=food, wallet=wallet, type="expense", amount=100, date=date.today())
        Transaction.objects.create(user=self.user, category=housing, wallet=wallet, type="expense", amount=95, date=date.today())
        rows = self.client.get(reverse("budgets")).context["rows"]
        names = [r["category"].name for r in rows]
        self.assertEqual(names[:2], ["Housing", "Food"])
        self.assertTrue(all(r["limit"] is None for r in rows[2:]))

    def test_categories_are_grouped_by_type(self):
        page = self.client.get(reverse("categories")).content.decode()
        self.assertLess(page.index("Expense categories"), page.index("Income categories"))
        self.assertLess(page.index("Housing"), page.index("Income categories"))
        self.assertGreater(page.index("Salary"), page.index("Income categories"))

    def test_dashboard_floating_buttons_keep_accessible_names(self):
        t = Transaction.objects.create(
            user=self.user, category=Category.objects.get(user=self.user, name="Food"),
            wallet=Wallet.objects.get(user=self.user, name="Cash"), type="expense", amount=5, date=date.today())
        page = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn('class="fab__label"', page)
        self.assertIn("Add income", page)

    def test_transaction_row_puts_the_wallet_in_the_details_line(self):
        Transaction.objects.create(
            user=self.user, category=Category.objects.get(user=self.user, name="Food"),
            wallet=Wallet.objects.get(user=self.user, name="Cash"), type="expense", amount=5, date=date.today(), note="Lunch")
        page = self.client.get(reverse("transactions")).content.decode()
        self.assertIn("· 💵 Cash · Lunch", page)


class NavigationClarityTests(TestCase):
    """Fixes from the UX/UI audit, zone 3: finding things."""

    def setUp(self):
        from .starter import create_starter_data
        self.user = get_user_model().objects.create_user(username="nv", email="nv@example.com", password="pass12345")
        create_starter_data(self.user)
        self.client.force_login(self.user)
        food = Category.objects.get(user=self.user, name="Food")
        health = Category.objects.get(user=self.user, name="Health")
        wallet = Wallet.objects.get(user=self.user, name="Cash")
        Transaction.objects.create(user=self.user, category=food, wallet=wallet, type="expense", amount=10, date=date.today(), note="Pizza night")
        Transaction.objects.create(user=self.user, category=health, wallet=wallet, type="expense", amount=20, date=date.today(), note="Pharmacy")

    def test_search_matches_notes_and_category_names(self):
        by_note = self.client.get(reverse("transactions"), {"q": "pizza"})
        self.assertEqual([t.note for t in by_note.context["transactions"]], ["Pizza night"])
        by_category = self.client.get(reverse("transactions"), {"q": "health"})
        self.assertEqual([t.note for t in by_category.context["transactions"]], ["Pharmacy"])

    def test_search_never_shows_another_users_transactions(self):
        other = get_user_model().objects.create_user(username="ot", email="ot@example.com", password="pass12345")
        from .starter import create_starter_data
        create_starter_data(other)
        Transaction.objects.create(
            user=other, category=Category.objects.get(user=other, name="Food"),
            wallet=Wallet.objects.get(user=other, name="Cash"), type="expense", amount=5, date=date.today(), note="Pizza secret")
        page = self.client.get(reverse("transactions"), {"q": "pizza"}).content.decode()
        self.assertNotIn("Pizza secret", page)

    def test_search_keeps_the_other_filters_and_the_exports(self):
        page = self.client.get(reverse("transactions"), {"q": "pizza", "type": "expense"}).content.decode()
        self.assertIn('name="type" value="expense"', page)
        self.assertIn("q=pizza", page)          # export links carry the search

    def test_app_menu_has_no_second_profile_tab_and_is_grouped(self):
        page = self.client.get(reverse("dashboard")).content.decode()
        subnav = page.split('<nav class="subnav">')[1].split("</nav>")[0]
        self.assertNotIn(">Profile</a>", subnav)
        self.assertEqual(subnav.count("subnav__sep"), 2)
        self.assertLess(subnav.index(">Budgets</a>"), subnav.index(">Categories</a>"))

    def test_public_navbar_offers_the_demo(self):
        self.client.logout()
        page = self.client.get("/").content.decode()
        nav = page.split('<nav class="nav">')[1].split("</nav>")[0]
        self.assertIn("Try the demo", nav)
        self.assertIn("demo", nav.split("Try the demo")[0].split("<form")[-1])


class FrictionFixesTests(TestCase):
    """Fixes from the UX/UI audit, zone 4."""

    def setUp(self):
        from .starter import create_starter_data
        self.user = get_user_model().objects.create_user(username="fr", email="fr@example.com", password="pass12345")
        create_starter_data(self.user)
        self.client.force_login(self.user)

    def test_expense_form_groups_amount_with_date_and_category_with_wallet(self):
        page = self.client.get(reverse("add_expense")).content.decode()
        order = [page.index(f'name="{n}"') for n in ("amount", "date", "category", "wallet")]
        self.assertEqual(order, sorted(order))
        self.assertIn("<!-- Amount + Date -->", page)
        self.assertIn("<!-- Category + Wallet -->", page)

    def test_budgets_month_picker_submits_by_itself_but_keeps_the_button(self):
        page = self.client.get(reverse("budgets")).content.decode()
        self.assertIn("data-autosubmit", page)
        self.assertIn(">Show</button>", page)

    def test_a_demo_visitor_is_asked_before_ending_the_demo(self):
        from accounts.demo import create_demo_user
        demo = create_demo_user()
        self.client.force_login(demo)
        page = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn('data-confirm="End the demo?', page)
        self.assertIn(">End demo</button>", page)

    def test_a_normal_user_still_sees_log_out_without_a_prompt(self):
        page = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn(">Log out</button>", page)
        self.assertNotIn("data-confirm", page)
