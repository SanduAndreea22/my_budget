"""Thin wrappers around Django's built-in password validators that keep
the exact same checks but replace the default, somewhat clinical wording
("Your password can't be entirely numeric.") with plain language that
matches the rest of the app's tone."""

from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    UserAttributeSimilarityValidator,
)
from django.core.exceptions import ValidationError


class FriendlyUserAttributeSimilarityValidator(UserAttributeSimilarityValidator):
    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError("Don't reuse your name or email as your password.", code="password_too_similar")

    def get_help_text(self):
        return "Don't reuse your name or email as your password."


class FriendlyMinimumLengthValidator(MinimumLengthValidator):
    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError(f"At least {self.min_length} characters.", code="password_too_short")

    def get_help_text(self):
        return f"At least {self.min_length} characters."


class FriendlyCommonPasswordValidator(CommonPasswordValidator):
    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError('Avoid common passwords like "12345678" or "password".', code="password_too_common")

    def get_help_text(self):
        return 'Avoid common passwords like "12345678" or "password".'


class FriendlyNumericPasswordValidator(NumericPasswordValidator):
    def validate(self, password, user=None):
        try:
            super().validate(password, user)
        except ValidationError:
            raise ValidationError("Mix in a letter or two — not just numbers.", code="password_entirely_numeric")

    def get_help_text(self):
        return "Mix in a letter or two — not just numbers."
