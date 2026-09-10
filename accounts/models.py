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

    class Meta:
        # email=unique=True above is case-sensitive at the DB level, but
        # every lookup in the app (login, password reset) matches
        # case-insensitively (email__iexact) — without this, two accounts
        # differing only by case (Bob@x.com / bob@x.com) could both exist
        # and silently confuse which one a login/reset actually targets.
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_customuser_email_ci_unique"),
        ]


