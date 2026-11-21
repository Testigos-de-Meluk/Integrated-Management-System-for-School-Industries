"""Django ORM models of the shared kernel."""

import uuid

from django.db import models
from django.db.models import Q


class AuditEntryModel(models.Model):
    """Insert-only audit log (NFR-08-01, RN-M1-05).

    A database trigger (migration 0002) rejects every UPDATE and DELETE, even from the
    application's own database user. ``user_id`` is a plain UUID, not a foreign key, so the shared
    kernel does not depend on the user accounts module and entries survive any change to users.
    """

    class ActorType(models.TextChoices):
        USER = "USER"
        SYSTEM = "SYSTEM"
        ANONYMOUS = "ANONYMOUS"

    class Result(models.TextChoices):
        SUCCESS = "SUCCESS"
        FAILURE = "FAILURE"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True)  # timestamptz, stored in UTC
    actor_type = models.CharField(max_length=10, choices=ActorType.choices)
    user_id = models.UUIDField(null=True, blank=True)
    actor_label = models.CharField(max_length=254, blank=True, default="")
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    action = models.CharField(max_length=20)
    entity_type = models.CharField(max_length=60)
    entity_id = models.CharField(max_length=60)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    result = models.CharField(max_length=10, choices=Result.choices, default=Result.SUCCESS)

    class Meta:
        db_table = "audit_entry"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["occurred_at"], name="audit_occurred_at_idx"),
            models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx"),
            models.Index(fields=["user_id"], name="audit_user_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(actor_type="USER") | Q(user_id__isnull=False),
                name="audit_user_actor_has_user_id",
            )
        ]

    def __str__(self) -> str:
        return f"{self.occurred_at:%Y-%m-%d %H:%M:%S} {self.action} {self.entity_type}"
