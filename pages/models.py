from django.conf import settings
from django.db import models


class FeedbackMessage(models.Model):
    """A message sent through the contact form. Read in Django admin; the app sends no email."""

    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)  # optional: only if the sender wants a reply
    message = models.TextField(max_length=2000)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback_messages")
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} · {self.name or 'anonymous'} · {self.message[:40]}"
