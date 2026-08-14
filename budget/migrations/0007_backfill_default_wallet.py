from django.db import migrations


def create_default_wallets(apps, schema_editor):
    Transaction = apps.get_model("budget", "Transaction")
    Wallet = apps.get_model("budget", "Wallet")

    user_ids = (
        Transaction.objects.filter(wallet__isnull=True)
        .values_list("user_id", flat=True)
        .distinct()
    )
    for user_id in user_ids:
        wallet, _ = Wallet.objects.get_or_create(user_id=user_id, name="Main")
        Transaction.objects.filter(user_id=user_id, wallet__isnull=True).update(wallet=wallet)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("budget", "0006_wallet_transaction_wallet"),
    ]

    operations = [
        migrations.RunPython(create_default_wallets, noop_reverse),
    ]
