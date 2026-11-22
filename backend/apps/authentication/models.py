"""Authentication state: OTPs, sessions and password resets.

Every secret in this module is stored **hashed**. Nothing here can be read back
out of the database, and nothing here writes a secret to a log.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class OTPPurpose(models.TextChoices):
    LOGIN = "LOGIN", "Login"
    ADMIN_MFA = "ADMIN_MFA", "Admin MFA"
    FORGOT_PASSWORD = "FORGOT_PASSWORD", "Forgot password"
    CHANGE_PASSWORD = "CHANGE_PASSWORD", "Change password"


class DeliveryChannel(models.TextChoices):
    SMS = "SMS", "SMS"
    EMAIL = "EMAIL", "Email"


class OTPVerification(models.Model):
    """A single issued one-time password.

    ``otp_hash`` is a Django password hash of the six digits: verification uses
    ``check_password``, which is constant-time and salted. A leaked database row
    therefore does not reveal a usable OTP.

    Reuse is prevented by ``is_verified``: a row can only be consumed once. A
    fresh OTP request marks the previous unconsumed rows for the same purpose as
    superseded so only the newest code is live.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="otps"
    )
    otp_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=32, choices=OTPPurpose.choices, db_index=True)
    delivery_channel = models.CharField(
        max_length=10, choices=DeliveryChannel.choices
    )
    destination = models.CharField(
        max_length=254,
        blank=True,
        default="",
        help_text="Masked in API responses; stores the mobile or email the OTP went to.",
    )
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "auth_otp_verification"
        verbose_name = "OTP verification"
        verbose_name_plural = "OTP verifications"
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=["user", "purpose", "is_verified"],
                name="otp_user_purpose_idx",
            ),
        ]

    def __str__(self):
        return f"{self.purpose} for {self.user_id} ({'used' if self.is_verified else 'live'})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_exhausted(self):
        return self.attempts >= self.max_attempts

    @property
    def is_usable(self):
        return not (self.is_verified or self.is_expired or self.is_exhausted)


class PasswordReset(models.Model):
    """A password-reset grant, created only after OTP verification.

    ``reset_token_hash`` lets the final step prove that the caller is the same
    browser that verified the OTP, without the raw token ever being stored.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_resets"
    )
    reset_token_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "auth_password_reset"
        verbose_name = "Password reset"
        verbose_name_plural = "Password resets"
        ordering = ("-created_at",)

    def __str__(self):
        return f"reset for {self.user_id} ({'used' if self.is_used else 'live'})"

    @property
    def is_usable(self):
        return not self.is_used and timezone.now() < self.expires_at


class OTPThrottle(models.Model):
    """Sliding-window counters for account-based and IP-based rate limiting.

    Stored in the database rather than in process memory so that the limit still
    holds when several gunicorn workers are running.
    """

    scope = models.CharField(max_length=32, db_index=True)
    key = models.CharField(max_length=254, db_index=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "auth_otp_throttle"
        verbose_name = "OTP throttle"
        verbose_name_plural = "OTP throttles"
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "key", "window_start"], name="throttle_unique_window"
            ),
        ]
        indexes = [models.Index(fields=["scope", "key"], name="throttle_scope_key_idx")]
