"""Public routes of the virtual assistant, mounted at /api/chatbot/."""

from django.urls import path

from .views import (
    EstimateView,
    PublicCatalogView,
    QuotationEmailView,
    QuotationPdfView,
    QuotationRequestView,
)

urlpatterns = [
    path("catalog/", PublicCatalogView.as_view(), name="chatbot-catalog"),
    path("estimate/", EstimateView.as_view(), name="chatbot-estimate"),
    path("quotations/", QuotationRequestView.as_view(), name="chatbot-quotation"),
    path("quotations/<uuid:quotation_id>/pdf/", QuotationPdfView.as_view(), name="chatbot-pdf"),
    path(
        "quotations/<uuid:quotation_id>/email/",
        QuotationEmailView.as_view(),
        name="chatbot-email",
    ),
]
