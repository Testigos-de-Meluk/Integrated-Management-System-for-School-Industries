"""Composition root of the Quotations module."""

from functools import lru_cache

from django.conf import settings

from modules.products.infrastructure.dependencies import product_catalog
from modules.quotations.application.approved_quotations_service import (
    ApprovedQuotationsService,
)
from modules.quotations.application.dispatch_estimator import MedianDispatchDateEstimator
from modules.quotations.application.estimators import (
    AiPriceEstimator,
    FallbackPriceEstimator,
    StatisticalPriceEstimator,
)
from modules.quotations.application.item_proposals import ItemProposer
from modules.quotations.application.quotation_request_service import QuotationRequestService
from modules.quotations.application.quotation_review_service import (
    CustomerQuotationsService,
    QuotationReviewService,
)
from modules.quotations.ports.inbound.approved_quotations import ApprovedQuotations
from modules.quotations.ports.inbound.customer_quotations import CustomerQuotations
from modules.quotations.ports.inbound.quotation_requests import QuotationRequests
from modules.quotations.ports.inbound.quotation_review import QuotationReview
from modules.quotations.ports.outbound.ports import DispatchDateEstimator, PriceEstimator
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger
from modules.shared_kernel.infrastructure.events.in_process_event_bus import event_bus
from modules.shared_kernel.infrastructure.llm import language_model
from modules.shared_kernel.infrastructure.notifications.celery_email_notifier import (
    CeleryEmailNotifier,
)

from .documents.reportlab_generator import ReportLabQuotationGenerator
from .persistence.dispatch_samples import WorkOrderDispatchSamples
from .persistence.repositories import (
    DjangoPriceHistory,
    DjangoQuotationNumberGenerator,
    DjangoQuotationRepository,
)
from .pricing.cached_estimator import CachedPriceEstimator


@lru_cache(maxsize=1)
def price_estimator() -> PriceEstimator:
    """Own history first; the AI only fills the gaps, using similar approved products."""
    history = DjangoPriceHistory()
    ai = AiPriceEstimator(
        language_model(), history, product_catalog(), settings.PRICE_LOOKBACK_DAYS
    )
    return FallbackPriceEstimator(
        [
            StatisticalPriceEstimator(history, settings.PRICE_LOOKBACK_DAYS),
            CachedPriceEstimator(
                ai, settings.AI_PRICE_CACHE_SECONDS, prefix=f"ai-price:{settings.LLM_MODEL}"
            ),
        ]
    )


@lru_cache(maxsize=1)
def dispatch_estimator() -> DispatchDateEstimator:
    """Median of real dispatches (FR-02-06), read from the work orders module."""
    # Imported here: the work orders module also imports this module (approved quotations).
    from modules.work_orders.infrastructure.dependencies import dispatch_history

    return MedianDispatchDateEstimator(WorkOrderDispatchSamples(dispatch_history()))


@lru_cache(maxsize=1)
def quotation_requests() -> QuotationRequests:
    """Public use cases of the virtual assistant."""
    return QuotationRequestService(
        repository=DjangoQuotationRepository(),
        numbers=DjangoQuotationNumberGenerator(),
        catalog=product_catalog(),  # inbound port of the products module
        price_estimator=price_estimator(),
        dispatch_estimator=dispatch_estimator(),
        documents=ReportLabQuotationGenerator(),
        notifier=CeleryEmailNotifier(),
        audit_logger=DatabaseAuditLogger(),
        validity_days=settings.QUOTATION_VALIDITY_DAYS,
        item_proposer=ItemProposer(language_model(), product_catalog()),
    )


@lru_cache(maxsize=1)
def quotation_review() -> QuotationReview:
    """Review by the Administrador."""
    # Imported here: the customers module also imports this module (customer history).
    from modules.customers.infrastructure.dependencies import customer_directory

    return QuotationReviewService(
        repository=DjangoQuotationRepository(),
        catalog=product_catalog(),
        customers=customer_directory(),  # inbound port of the customers module
        price_estimator=price_estimator(),
        dispatch_estimator=dispatch_estimator(),
        documents=ReportLabQuotationGenerator(),
        notifier=CeleryEmailNotifier(),
        events=event_bus,
        audit_logger=DatabaseAuditLogger(),
        validity_days=settings.QUOTATION_VALIDITY_DAYS,
    )


@lru_cache(maxsize=1)
def approved_quotations() -> ApprovedQuotations:
    """For the work orders module: approved quotations and linking their customer."""
    from modules.customers.infrastructure.dependencies import customer_directory

    return ApprovedQuotationsService(
        DjangoQuotationRepository(), customer_directory(), DatabaseAuditLogger()
    )


@lru_cache(maxsize=1)
def customer_quotations() -> CustomerQuotations:
    """For other modules: the quotations of a customer."""
    return CustomerQuotationsService(DjangoQuotationRepository())
