from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
import os

def user_image_upload_path(instance, filename):
    return os.path.join("Users", instance.username, filename)

def validate_image_size(image):
    max_bytes = 2 * 1024 * 1024
    if image.size > max_bytes:
        raise ValidationError("Image must be 2MB or smaller.")

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    description = models.TextField("Description", max_length=600, default="", blank=True)
    image = models.ImageField(
        upload_to=user_image_upload_path,
        default="",
        blank=True,
        null=True,
        validators=[validate_image_size],
    )

    def __str__(self):
        return self.username

    CURRENCY_CHOICES = [
        ("RON", "RON (Romanian Leu)"),
        ("EUR", "EUR (€)"),
        ("USD", "USD ($)"),
        ("GBP", "GBP (£)"),
    ]

    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="RON")

    def delete(self, *args, **kwargs):
        # budget.Category/Wallet are PROTECTed from Transaction,
        # BudgetLimit and RecurringTransaction (so a user can't delete a
        # category/wallet still in use) — but that same protection also
        # blocks Django's own User -> Category/Wallet CASCADE when the
        # user itself is deleted: those protecting rows still exist at
        # collection time, even though they'd be deleted too via their
        # own direct user=CASCADE. Clearing them first lets deleting a
        # user (admin, shell, a future "delete my account" feature)
        # cascade cleanly instead of raising ProtectedError. Imported
        # locally to avoid accounts depending on budget at module load.
        from budget.models import BudgetLimit, RecurringTransaction, Transaction

        Transaction.objects.filter(user=self).delete()
        BudgetLimit.objects.filter(user=self).delete()
        RecurringTransaction.objects.filter(user=self).delete()
        return super().delete(*args, **kwargs)

    class Meta:
        # email=unique=True above is case-sensitive at the DB level, but
        # every lookup in the app (login, password reset) matches
        # case-insensitively (email__iexact) — without this, two accounts
        # differing only by case (Bob@x.com / bob@x.com) could both exist
        # and silently confuse which one a login/reset actually targets.
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_customuser_email_ci_unique"),
        ]


