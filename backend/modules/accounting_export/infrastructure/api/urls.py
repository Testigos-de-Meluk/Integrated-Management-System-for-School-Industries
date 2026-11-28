"""REST routes of the Accounting Export module, mounted at /api/accounting-export/."""

from django.urls import path

from .views import QueueView

urlpatterns = [
    path("queue/", QueueView.as_view(), name="export-queue"),
]
