"""Django ORM models of the Accounting Export module.

The work order is referenced by a plain UUID (work orders module), never by a foreign key.
"""

import uuid

from django.db import models


class QueueEntryModel(models.Model):
    """PROCESSING_QUEUE_ENTRY of the data model: one row per O.T., never deleted."""

    class Status(models.TextChoices):
        PENDING_EXPORT = "PENDING_EXPORT", "Pendiente de exportar"
        EXPORTED = "EXPORTED", "Exportada"
        WITHDRAWN = "WITHDRAWN", "Retirada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order_id = models.UUIDField(unique=True)  # US 2.30.4: no duplicates
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_EXPORT)
    enqueued_at = models.DateTimeField()
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    exported_at = models.DateTimeField(null=True, blank=True)
    export_batch_id = models.UUIDField(null=True, blank=True)  # EXPORT_BATCH arrives in 5d

    class Meta:
        db_table = "processing_queue_entry"
        indexes = [models.Index(fields=["status", "enqueued_at"], name="queue_status_date_idx")]

    def __str__(self) -> str:
        return f"{self.work_order_id} ({self.status})"
