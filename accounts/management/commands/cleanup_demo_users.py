from django.core.management.base import BaseCommand

from accounts.demo import cleanup_old_demo_users


class Command(BaseCommand):
    help = "Delete demo accounts older than 24 hours. Safe to run from a daily scheduler."

    def handle(self, *args, **options):
        self.stdout.write(f"Deleted {cleanup_old_demo_users()} demo account(s).")
