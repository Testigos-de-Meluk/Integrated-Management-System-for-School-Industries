"""Django ORM models of the Authentication module.

``user_id`` columns are plain UUIDs (indexed), not foreign keys to ``app_user``: the user table
belongs to another module, and modules only talk through their ports.
"""

import uuid

from django.db import models


class SessionModel(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        TERMINATED = "TERMINATED"

    class Reason(models.TextChoices):
        LOGOUT = "LOGOUT"
        INACTIVITY = "INACTIVITY"
        NEW_LOGIN = "NEW_LOGIN"
        ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
        PASSWORD_CHANGED = "PASSWORD_CHANGED"
        TOKEN_REUSE = "TOKEN_REUSE"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    refresh_token_id = models.CharField(max_length=64)
    created_at = models.DateTimeField()
    last_activity_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    termination_reason = models.CharField(
        max_length=20, choices=Reason.choices, blank=True, default=""
    )
    terminated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "session"
        indexes = [models.Index(fields=["user_id", "status"], name="session_user_status_idx")]

    def __str__(self) -> str:
        return f"Session {self.id} ({self.status})"


class TotpEnrollmentModel(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        CONFIRMED = "CONFIRMED"
        EXPIRED = "EXPIRED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True)  # at most one enrollment per user
    encrypted_secret = models.TextField()  # Fernet (AES-128-CBC + HMAC), never the plain secret
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_step = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "totp_enrollment"

    def __str__(self) -> str:
        return f"TOTP {self.user_id} ({self.status})"
