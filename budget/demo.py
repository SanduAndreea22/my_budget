"""Example data for demo accounts (the same story the landing-page screenshots show)."""
from datetime import date, timedelta
from decimal import Decimal as D

from django.urls import reverse

from .models import ActivityLog, BudgetLimit, Category, SavingsGoal, Transaction, Wallet
from .starter import create_starter_data


def _month_start(today, months_ago):
    y, m = today.year, today.month - months_ago
    while m <= 0:
        y, m = y - 1, m + 12
    return date(y, m, 1)


def create_demo_data(user, today=None):
    today = today or date.today()
    create_starter_data(user)
    cash = Wallet.objects.get(user=user, name="Cash")
    card, _ = Wallet.objects.get_or_create(user=user, name="Card", defaults={"icon": "💳"})
    cat = {c.name: c for c in Category.objects.filter(user=user)}
    m0 = today.replace(day=1)

    def tx(name, amount, kind, when, note, wallet=card):
        Transaction.objects.create(
            user=user, wallet=wallet, category=cat[name], amount=D(str(amount)),
            type=kind, date=when, note=note,
        )

    # three earlier months, so the trend chart has a story
    for ago, (food, transport, fun, shop) in {3: (512.40, 208.00, 138.50, 187.90), 2: (561.30, 161.20, 171.00, 239.60), 1: (607.80, 189.50, 76.40, 204.30)}.items():
        b = _month_start(today, ago)
        tx("Salary", 6380, "income", b, "Salary")
        tx("Housing", 1750, "expense", b + timedelta(days=1), "Rent")
        tx("Bills", 238.40, "expense", b + timedelta(days=4), "Utilities")
        tx("Food", food, "expense", b + timedelta(days=9), "Groceries")
        tx("Transport", transport, "expense", b + timedelta(days=11), "Fuel & metro")
        tx("Entertainment", fun, "expense", b + timedelta(days=15), "Cinema & games")
        tx("Shopping", shop, "expense", b + timedelta(days=19), "Clothes")

    # this month
    def ago(n):
        return max(m0, today - timedelta(days=n))

    tx("Salary", 6380, "income", m0, "Salary")
    tx("Housing", 1750, "expense", min(today, m0 + timedelta(days=1)), "Rent")
    tx("Bills", 238.40, "expense", ago(8), "Utilities")
    tx("Food", 214.30, "expense", ago(7), "Weekly groceries")
    tx("Shopping", 312.40, "expense", ago(6), "New sneakers")
    tx("Transport", 142.00, "expense", ago(5), "Monthly metro pass")
    tx("Food", 86.50, "expense", ago(3), "Dinner out")
    tx("Entertainment", 94.50, "expense", ago(2), "Cinema night")
    tx("Food", 119.80, "expense", ago(1), "Groceries")
    tx("Food", 63.90, "expense", today, "Lunch & coffee", cash)
    tx("Health", 58.70, "expense", today, "Pharmacy", cash)

    # budgets: one near its limit, one over, the rest on track
    for name, limit in [("Food", 650), ("Transport", 300), ("Shopping", 250), ("Entertainment", 200), ("Housing", 1850)]:
        BudgetLimit.objects.create(user=user, category=cat[name], month=m0, limit=D(limit))

    SavingsGoal.objects.create(user=user, name="Emergency fund", target_amount=D(10000), saved_amount=D(6420),
                               target_date=date(today.year + 1, 3, 1))
    SavingsGoal.objects.create(user=user, name="Summer trip", target_amount=D(2500), saved_amount=D(2500),
                               target_date=date(today.year + 1, 6, 1))
    SavingsGoal.objects.create(user=user, name="New laptop", target_amount=D(4200), saved_amount=D(1260),
                               target_date=date(today.year + 1, 1, 1))


def tour_steps(user):
    """The "Things to try" guide shown to demo visitors. A step is done when the visitor really did it
    (the seed data is created without activity-log entries, so it never counts)."""
    done = set(ActivityLog.objects.filter(user=user).values_list("model_name", "action"))
    did = lambda *pairs: any(p in done for p in pairs)

    goal = SavingsGoal.objects.filter(user=user, name="New laptop").first()
    if goal and goal.saved_amount < goal.target_amount:
        diff = goal.target_amount - goal.saved_amount
        gap = f"{diff:,.0f}" if diff == diff.to_integral_value() else f"{diff:,.2f}"
        goal_hint = f'Add {gap} {user.currency} to "{goal.name}" to reach your target and see a small celebration.'
    else:
        goal_hint = "Add money to one of your savings goals and watch the bar fill."

    steps = [
        {"key": "expense", "title": "Add an expense",
         "hint": f"Add 100 {user.currency} under Food. Watch your Food budget get near its limit, and the totals and chart update.",
         "cta": "Add expense", "url": reverse("add_expense"), "done": did(("Transaction", "create"))},
        {"key": "budget", "title": "Give Health a budget",
         "hint": f"Health has no budget yet. Set a limit (for example 100 {user.currency}) and a progress bar appears.",
         "cta": "Set a budget", "url": reverse("budget_add"), "done": did(("Budget Limit", "create"), ("Budget Limit", "update"))},
        {"key": "goal", "title": "Finish a savings goal",
         "hint": goal_hint, "cta": "Open goals", "url": reverse("savings_goals"), "done": did(("Savings Goal", "update"))},
        {"key": "recurring", "title": "Add a recurring transaction",
         "hint": f"Add a subscription, for example 40 {user.currency} a month. From then on it is added for you every month.",
         "cta": "Add recurring", "url": reverse("recurring_add"), "done": did(("Recurring Transaction", "create"))},
    ]
    return {"steps": steps, "done_count": sum(s["done"] for s in steps), "total": len(steps)}
