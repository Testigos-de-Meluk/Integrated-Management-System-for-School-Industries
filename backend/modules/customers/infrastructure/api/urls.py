"""REST routes of the Customers module, mounted at /api/customers/."""

from django.urls import path

from .views import (
    CustomerActivateView,
    CustomerByTaxIdView,
    CustomerDeactivateView,
    CustomerDetailView,
    CustomerHistoryView,
    CustomerListCreateView,
    NoteDetailView,
    NoteListCreateView,
)

urlpatterns = [
    path("", CustomerListCreateView.as_view(), name="customer-list"),
    path("by-tax-id/<str:tax_id>/", CustomerByTaxIdView.as_view(), name="customer-by-tax-id"),
    path("<uuid:customer_id>/", CustomerDetailView.as_view(), name="customer-detail"),
    path("<uuid:customer_id>/activate/", CustomerActivateView.as_view(), name="customer-activate"),
    path(
        "<uuid:customer_id>/deactivate/",
        CustomerDeactivateView.as_view(),
        name="customer-deactivate",
    ),
    path("<uuid:customer_id>/history/", CustomerHistoryView.as_view(), name="customer-history"),
    path("<uuid:customer_id>/notes/", NoteListCreateView.as_view(), name="customer-notes"),
    path(
        "<uuid:customer_id>/notes/<uuid:note_id>/",
        NoteDetailView.as_view(),
        name="customer-note-detail",
    ),
]
