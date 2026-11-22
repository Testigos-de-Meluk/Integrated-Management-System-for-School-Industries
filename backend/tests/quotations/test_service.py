"""Public quotation use cases with in-memory adapters (no database, no PDF library)."""

from decimal import Decimal
from uuid import uuid4

import pytest

from modules.products.ports.inbound.product_catalog import CatalogItem, ProductCatalog
from modules.quotations.application.estimators import (
    FallbackPriceEstimator,
    StatisticalPriceEstimator,
)
from modules.quotations.application.quotation_request_service import QuotationRequestService
from modules.quotations.domain.exceptions import InvalidQuotationItems, QuotationNotFound
from modules.quotations.ports.inbound.quotation_requests import (
    RequestedItem,
    RequestQuotationCommand,
)
from modules.quotations.ports.outbound.ports import (
    DispatchDateEstimator,
    PriceEstimator,
    PriceHistory,
    QuotationDocumentGenerator,
    QuotationNumberGenerator,
    QuotationRepository,
)
from modules.shared_kernel.domain.audit import ActorType
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.money import PriceRange
from modules.shared_kernel.domain.pagination import Page

from ..shared_fakes import SpyAuditLogger, SpyNotifier

CHAIR = CatalogItem(uuid4(), "SIL-001", "Silla escolar", "Unidad")
DESK = CatalogItem(uuid4(), "MES-002", "Mesa bipersonal", "Unidad")


class FakeCatalog(ProductCatalog):
    def search_selectable(self, text, page_request):
        return Page([CHAIR, DESK], 2, page_request)

    def selectable_by_ids(self, product_ids):
        return {p.id: p for p in (CHAIR, DESK) if p.id in product_ids}


class MemoryRepository(QuotationRepository):
    def __init__(self):
        self.items = {}

    def add(self, quotation):
        self.items[quotation.id] = quotation

    def get(self, quotation_id):
        return self.items.get(quotation_id)


class Numbers(QuotationNumberGenerator):
    def __init__(self):
        self.last = 0

    def next_number(self, year):
        self.last += 1
        return f"COT-{year}-{self.last:04d}"


class FixedHistory(PriceHistory):
    def approved_unit_prices(self, product_id, since):
        return [Decimal(170000), Decimal(190000)] if product_id == CHAIR.id else []


class BrokenEstimator(PriceEstimator):
    def estimate(self, product_id, quantity):
        raise RuntimeError("AI provider down")


class NoDispatch(DispatchDateEstimator):
    def suggest(self, items, today):
        return None


class FakePdf(QuotationDocumentGenerator):
    def preliminary_pdf(self, quotation):
        return b"%PDF-fake " + quotation.number.encode()


@pytest.fixture
def deps():
    return {"repository": MemoryRepository(), "notifier": SpyNotifier(), "audit": SpyAuditLogger()}


@pytest.fixture
def service(deps):
    estimator = FallbackPriceEstimator(
        [BrokenEstimator(), StatisticalPriceEstimator(FixedHistory())]
    )
    return QuotationRequestService(
        repository=deps["repository"],
        numbers=Numbers(),
        catalog=FakeCatalog(),
        price_estimator=estimator,
        dispatch_estimator=NoDispatch(),
        documents=FakePdf(),
        notifier=deps["notifier"],
        audit_logger=deps["audit"],
    )


def command(**overrides):
    data = {
        "full_name": "Laura Méndez",
        "email": "laura@colegio.edu.co",
        "phone": "310 456 7890",
        "items": (RequestedItem(CHAIR.id, 40), RequestedItem(DESK.id, 10)),
        "data_consent": True,
    } | overrides
    return RequestQuotationCommand(**data)


def test_estimate_uses_the_fallback_strategy_and_marks_unpriced_items(service):
    estimate = service.estimate((RequestedItem(CHAIR.id, 40), RequestedItem(DESK.id, 10)))

    chair, desk = estimate.items
    assert (chair.unit_price_min, chair.unit_price_max) == ("170000", "190000")
    assert desk.unit_price_min is None  # "Precio por confirmar"
    assert (estimate.total_min, estimate.total_max, estimate.unpriced_items) == (
        "6800000",
        "7600000",
        1,
    )


def test_request_saves_a_numbered_pending_quotation_and_audits_it(service, deps):
    first = service.request_quotation(command(), "10.0.0.5")
    second = service.request_quotation(command(), "10.0.0.5")

    assert first.number.endswith("-0001") and second.number.endswith("-0002")
    record = deps["audit"].records[0]
    assert record.resolved_actor_type is ActorType.ANONYMOUS and record.source_ip == "10.0.0.5"


def test_repeated_products_are_merged(service):
    view = service.estimate((RequestedItem(CHAIR.id, 5), RequestedItem(CHAIR.id, 7)))

    assert [i.quantity for i in view.items] == [12]


def test_consent_is_required(service):
    with pytest.raises(ValidationError) as error:
        service.request_quotation(command(data_consent=False), None)

    assert "data_consent" in error.value.errors


def test_unavailable_products_are_rejected(service):
    with pytest.raises(InvalidQuotationItems):
        service.estimate((RequestedItem(uuid4(), 3),))


def test_document_requires_the_access_key_and_email_attaches_the_pdf(service, deps):
    view = service.request_quotation(command(), None)

    with pytest.raises(QuotationNotFound):
        service.document(view.id, "wrong")
    assert service.document(view.id, view.access_key).content.startswith(b"%PDF")

    assert service.email_document(view.id, view.access_key) == "laura@colegio.edu.co"
    attachment = deps["notifier"].sent[0].attachments[0]
    assert attachment.filename == f"{view.number}.pdf"


def test_price_range_sum_is_exact():
    assert PriceRange(Decimal(1), Decimal(2)) + PriceRange(Decimal(3), Decimal(4)) == PriceRange(
        Decimal(4), Decimal(6)
    )
