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
    export_batch_id = models.UUIDField(null=True, blank=True)  # ExportBatchModel, same module

    class Meta:
        db_table = "processing_queue_entry"
        indexes = [models.Index(fields=["status", "enqueued_at"], name="queue_status_date_idx")]

    def __str__(self) -> str:
        return f"{self.work_order_id} ({self.status})"


class ExportBatchModel(models.Model):
    """EXPORT_BATCH of the data model: one generated file, kept to be downloaded again."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_name = models.CharField(max_length=100)
    content_type = models.CharField(max_length=100)
    content = models.BinaryField()
    created_at = models.DateTimeField()
    created_by_id = models.UUIDField(null=True, blank=True)  # user_accounts module
    created_by_name = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        db_table = "export_batch"
        indexes = [models.Index(fields=["-created_at"], name="export_batch_created_idx")]

    def __str__(self) -> str:
        return self.file_name
