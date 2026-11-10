"""Example data for demo accounts (the same story the landing-page screenshots show)."""
from datetime import date, timedelta
from decimal import Decimal as D

from .models import BudgetLimit, Category, SavingsGoal, Transaction, Wallet
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
    for ago, (food, transport, fun, shop) in {3: (520, 210, 140, 190), 2: (560, 160, 170, 240), 1: (610, 190, 75, 205)}.items():
        b = _month_start(today, ago)
        tx("Salary", 6400, "income", b, "Salary")
        tx("Housing", 1800, "expense", b + timedelta(days=1), "Rent")
        tx("Bills", 230, "expense", b + timedelta(days=4), "Utilities")
        tx("Food", food, "expense", b + timedelta(days=9), "Groceries")
        tx("Transport", transport, "expense", b + timedelta(days=11), "Fuel & metro")
        tx("Entertainment", fun, "expense", b + timedelta(days=15), "Cinema & games")
        tx("Shopping", shop, "expense", b + timedelta(days=19), "Clothes")

    # this month
    def ago(n):
        return max(m0, today - timedelta(days=n))

    tx("Salary", 6400, "income", m0, "Salary")
    tx("Housing", 1800, "expense", min(today, m0 + timedelta(days=1)), "Rent")
    tx("Bills", 230, "expense", ago(8), "Utilities")
    tx("Food", 210, "expense", ago(7), "Weekly groceries")
    tx("Shopping", 310, "expense", ago(6), "New sneakers")
    tx("Transport", 140, "expense", ago(5), "Monthly metro pass")
    tx("Food", 85, "expense", ago(3), "Dinner out")
    tx("Entertainment", 95, "expense", ago(2), "Cinema night")
    tx("Food", 120, "expense", ago(1), "Groceries")
    tx("Food", 64.5, "expense", today, "Lunch & coffee", cash)
    tx("Health", 60, "expense", today, "Pharmacy", cash)

    # budgets: one near its limit, one over, the rest on track
    for name, limit in [("Food", 600), ("Transport", 300), ("Shopping", 250), ("Entertainment", 200), ("Housing", 1900)]:
        BudgetLimit.objects.create(user=user, category=cat[name], month=m0, limit=D(limit))

    SavingsGoal.objects.create(user=user, name="Emergency fund", target_amount=D(10000), saved_amount=D(6500),
                               target_date=date(today.year + 1, 3, 1))
    SavingsGoal.objects.create(user=user, name="Summer trip", target_amount=D(2500), saved_amount=D(2500),
                               target_date=date(today.year + 1, 6, 1))
    SavingsGoal.objects.create(user=user, name="New laptop", target_amount=D(4000), saved_amount=D(1200),
                               target_date=date(today.year + 1, 1, 1))
