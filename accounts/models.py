from django.contrib.auth.models import AbstractUser
from django.db import models
import os

def user_image_upload_path(instance, filename):
    return os.path.join("Users", instance.username, filename)

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    description = models.TextField("Description", max_length=600, default="", blank=True)
    image = models.ImageField(
        upload_to=user_image_upload_path,
        default="default/user.jpg",
        blank=True,
        null=True
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


