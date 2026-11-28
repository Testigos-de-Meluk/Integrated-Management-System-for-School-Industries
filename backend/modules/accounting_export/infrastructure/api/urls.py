"""REST routes of the Accounting Export module, mounted at /api/accounting-export/."""

from django.urls import path

from .views import BatchesView, BatchFileView, QueueView

urlpatterns = [
    path("queue/", QueueView.as_view(), name="export-queue"),
    path("batches/", BatchesView.as_view(), name="export-batches"),
    path("batches/<uuid:batch_id>/file/", BatchFileView.as_view(), name="export-batch-file"),
]
