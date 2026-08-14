from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from budget.views import generate_due_recurring_transactions

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Generate any due recurring transactions (subscriptions, salaries) "
        "for every user. The app also does this automatically when a user "
        "opens their dashboard, so this command is only needed if you want "
        "transactions to appear on schedule even for users who haven't "
        "logged in yet — e.g. by running it daily from cron."
    )

    def handle(self, *args, **options):
        count = 0
        for user in User.objects.all():
            count += 1
            generate_due_recurring_transactions(user)
        self.stdout.write(self.style.SUCCESS(f"Checked recurring transactions for {count} user(s)."))
