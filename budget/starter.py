"""Starter data for a brand-new account.

A new user used to need three forms (category, wallet, then the amount)
before logging a first transaction. Giving every new account a "Cash"
wallet and a handful of common categories lets the very first click on
"Add income" / "Add expense" land on a usable form. Everything here can be
renamed or deleted like any other record.
"""
from django.db import transaction

from .models import Category, Wallet

STARTER_WALLET = {"name": "Cash", "icon": "💵"}

STARTER_CATEGORIES = [
    # (name, type, icon, color)
    ("Salary", Category.INCOME, "💼", "#22c55e"),
    ("Other income", Category.INCOME, "💰", "#14b8a6"),
    ("Food", Category.EXPENSE, "🍔", "#f59e0b"),
    ("Housing", Category.EXPENSE, "🏠", "#6366f1"),
    ("Transport", Category.EXPENSE, "🚗", "#0ea5e9"),
    ("Bills", Category.EXPENSE, "💡", "#eab308"),
    ("Shopping", Category.EXPENSE, "🛍️", "#ec4899"),
    ("Entertainment", Category.EXPENSE, "🎬", "#a855f7"),
    ("Health", Category.EXPENSE, "💊", "#ef4444"),
]


@transaction.atomic
def create_starter_data(user):
    """Create the default wallet and categories for ``user``.

    Idempotent: uses get_or_create on the (user, name) uniqueness both
    models already enforce, so calling it twice never duplicates anything.
    """
    Wallet.objects.get_or_create(
        user=user, name=STARTER_WALLET["name"], defaults={"icon": STARTER_WALLET["icon"]}
    )
    for name, tx_type, icon, color in STARTER_CATEGORIES:
        Category.objects.get_or_create(
            user=user, name=name, defaults={"type": tx_type, "icon": icon, "color": color}
        )
