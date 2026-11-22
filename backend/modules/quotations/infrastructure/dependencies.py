"""Composition root of the Quotations module."""

from functools import lru_cache

from django.conf import settings

from modules.products.infrastructure.dependencies import product_catalog
from modules.quotations.application.estimators import (
    FallbackPriceEstimator,
    StatisticalPriceEstimator,
)
from modules.quotations.application.quotation_request_service import QuotationRequestService
from modules.quotations.ports.inbound.quotation_requests import QuotationRequests
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger
from modules.shared_kernel.infrastructure.notifications.celery_email_notifier import (
    CeleryEmailNotifier,
)

from .documents.reportlab_generator import ReportLabQuotationGenerator
from .persistence.repositories import (
    DjangoPriceHistory,
    DjangoQuotationNumberGenerator,
    DjangoQuotationRepository,
    NoHistoryDispatchDateEstimator,
)


@lru_cache(maxsize=1)
def quotation_requests() -> QuotationRequests:
    """Public use cases of the virtual assistant."""
    price_estimator = FallbackPriceEstimator(
        [
            # Sub-step 4c adds the AI strategy here, in front of the statistical fallback.
            StatisticalPriceEstimator(DjangoPriceHistory(), settings.PRICE_LOOKBACK_DAYS),
        ]
    )
    return QuotationRequestService(
        repository=DjangoQuotationRepository(),
        numbers=DjangoQuotationNumberGenerator(),
        catalog=product_catalog(),  # inbound port of the products module
        price_estimator=price_estimator,
        dispatch_estimator=NoHistoryDispatchDateEstimator(),  # median arrives in step 5
        documents=ReportLabQuotationGenerator(),
        notifier=CeleryEmailNotifier(),
        audit_logger=DatabaseAuditLogger(),
        validity_days=settings.QUOTATION_VALIDITY_DAYS,
    )
