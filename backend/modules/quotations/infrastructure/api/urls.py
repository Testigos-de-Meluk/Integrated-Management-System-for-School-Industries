"""REST routes of the Quotations module, mounted at /api/quotations/.

The public assistant uses /api/chatbot/ instead (chatbot module).
"""

from django.urls import path

from .views import (
    QuotationApproveView,
    QuotationCustomerView,
    QuotationDetailView,
    QuotationListView,
    QuotationModifyView,
    QuotationPdfView,
    QuotationRejectView,
)

urlpatterns = [
    path("", QuotationListView.as_view(), name="quotation-list"),
    path("<uuid:quotation_id>/", QuotationDetailView.as_view(), name="quotation-detail"),
    path("<uuid:quotation_id>/modify/", QuotationModifyView.as_view(), name="quotation-modify"),
    path("<uuid:quotation_id>/approve/", QuotationApproveView.as_view(), name="quotation-approve"),
    path("<uuid:quotation_id>/reject/", QuotationRejectView.as_view(), name="quotation-reject"),
    path(
        "<uuid:quotation_id>/customer/", QuotationCustomerView.as_view(), name="quotation-customer"
    ),
    path("<uuid:quotation_id>/pdf/", QuotationPdfView.as_view(), name="quotation-pdf"),
]
