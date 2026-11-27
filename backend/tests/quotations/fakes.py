"""In-memory adapters shared by the quotation use-case tests (no database, no PDF library)."""

from decimal import Decimal
from uuid import uuid4

from modules.customers.ports.inbound.customer_directory import CustomerDirectory, CustomerSummary
from modules.products.ports.inbound.product_catalog import CatalogItem, ProductCatalog
from modules.quotations.ports.outbound.ports import (
    DispatchDateEstimator,
    PriceEstimator,
    PriceHistory,
    PriceSample,
    QuotationDocumentGenerator,
    QuotationNumberGenerator,
    QuotationRepository,
)
from modules.shared_kernel.domain.document_numbers import document_number
from modules.shared_kernel.domain.pagination import Page
from modules.shared_kernel.ports.outbound.language_model import LanguageModel, LanguageModelError

CHAIR = CatalogItem(uuid4(), "SIL-001", "Silla escolar", "Unidad")
DESK = CatalogItem(uuid4(), "MES-002", "Mesa bipersonal", "Unidad")
BOARD = CatalogItem(uuid4(), "TAB-003", "Tablero acrílico", "Unidad")


class FakeCatalog(ProductCatalog):
    def search_selectable(self, text, page_request):
        return Page([CHAIR, DESK, BOARD], 3, page_request)

    def all_selectable(self, limit=500):
        return [CHAIR, DESK, BOARD]

    def selectable_by_ids(self, product_ids):
        return {p.id: p for p in (CHAIR, DESK, BOARD) if p.id in product_ids}


class MemoryRepository(QuotationRepository):
    def __init__(self):
        self.items = {}

    def add(self, quotation):
        self.items[quotation.id] = quotation

    def get(self, quotation_id):
        return self.items.get(quotation_id)

    def update(self, quotation):
        self.items[quotation.id] = quotation

    def search(self, filters, page_request):
        found = sorted(self.items.values(), key=lambda q: q.issued_at, reverse=True)
        if filters.status:
            found = [q for q in found if q.status.value == filters.status]
        return Page(found[: page_request.size], len(found), page_request)

    def for_customer(self, customer_id, page_request):
        found = [q for q in self.items.values() if q.customer_id == customer_id]
        return Page(found, len(found), page_request)

    def search_approved(self, text, excluded_ids, page_request):
        found = [
            q
            for q in self.items.values()
            if q.status.value == "APPROVED"
            and q.id not in excluded_ids
            and (not text or text.lower() in q.number.lower())
        ]
        return Page(found[: page_request.size], len(found), page_request)


class Numbers(QuotationNumberGenerator):
    def __init__(self):
        self.last = 0

    def next_number(self, issued_at):
        self.last += 1
        return document_number("COT", issued_at, self.last)


class FixedHistory(PriceHistory):
    def approved_unit_prices(self, product_id, since):
        return [Decimal(170000), Decimal(190000)] if product_id == CHAIR.id else []

    def reference_samples(self, since, limit):
        return [PriceSample(CHAIR.id, CHAIR.code, CHAIR.name, "Unidad", 40, Decimal(180000))]


class BrokenEstimator(PriceEstimator):
    def estimate(self, requests):
        raise RuntimeError("AI provider down")


class FakeLanguageModel(LanguageModel):
    """Answers a fixed JSON and records what it was sent (to check no personal data leaves)."""

    def __init__(self, answer=None, error=False, available=True):
        self.answer = answer or {}
        self.error = error
        self._available = available
        self.prompts: list[str] = []

    @property
    def available(self):
        return self._available

    def complete_json(self, system, user, max_tokens=1500):
        self.prompts.append(user)
        if self.error:
            raise LanguageModelError("down")
        return self.answer


class NoDispatch(DispatchDateEstimator):
    def suggest(self, items, today):
        return None


class FakePdf(QuotationDocumentGenerator):
    def preliminary_pdf(self, quotation):
        return b"%PDF-fake " + quotation.number.encode()

    def formal_pdf(self, quotation):
        return b"%PDF-formal " + quotation.number.encode()


class FakeCustomers(CustomerDirectory):
    def __init__(self, *customers: CustomerSummary):
        self.customers = {c.id: c for c in customers}

    def by_id(self, customer_id):
        return self.customers.get(customer_id)

    def by_tax_id(self, tax_id):
        digits = tax_id.replace(".", "").replace("-", "")
        return next(
            (c for c in self.customers.values() if c.tax_id.replace("-", "").startswith(digits)),
            None,
        )
