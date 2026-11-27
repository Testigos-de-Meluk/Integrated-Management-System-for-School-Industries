"""Outbound ports of the Quotations module."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from modules.quotations.domain.pricing import PriceEstimate
from modules.quotations.domain.quotation import Quotation
from modules.quotations.ports.inbound.quotation_review import QuotationFilters
from modules.shared_kernel.domain.pagination import Page, PageRequest


class QuotationRepository(ABC):
    @abstractmethod
    def add(self, quotation: Quotation) -> None: ...

    @abstractmethod
    def get(self, quotation_id: UUID) -> Quotation | None: ...

    @abstractmethod
    def update(self, quotation: Quotation) -> None:
        """Saves the header and replaces the items."""

    @abstractmethod
    def search(self, filters: QuotationFilters, page_request: PageRequest) -> Page[Quotation]:
        """One page matching every filter, newest first."""

    @abstractmethod
    def for_customer(self, customer_id: UUID, page_request: PageRequest) -> Page[Quotation]:
        """Quotations linked to a customer, newest first."""

    @abstractmethod
    def search_approved(
        self, text: str | None, excluded_ids: frozenset[UUID], page_request: PageRequest
    ) -> Page[Quotation]:
        """APPROVED quotations not in ``excluded_ids``, newest approval first; ``text`` matches
        the number, requester name, institution or NIT."""


class QuotationNumberGenerator(ABC):
    """``COT-YYYYMMDD-NNNNN``: local issue date + global consecutive that never restarts."""

    @abstractmethod
    def next_number(self, issued_at: datetime) -> str: ...


@dataclass(frozen=True, slots=True)
class PriceSample:
    """A final unit price of an approved quotation line (reference for the AI estimate)."""

    product_id: UUID
    product_code: str
    description: str
    unit_of_measure: str
    quantity: int
    unit_price: Decimal


class PriceHistory(ABC):
    @abstractmethod
    def approved_unit_prices(self, product_id: UUID, since: datetime) -> list[Decimal]:
        """Final unit prices of APPROVED quotations since ``since`` (newest first)."""

    @abstractmethod
    def reference_samples(self, since: datetime, limit: int) -> list[PriceSample]:
        """Recent approved lines of any product, newest first, at most one per product."""


#: (product id, quantity)
PriceRequest = tuple[UUID, int]


class PriceEstimator(ABC):
    """Strategy (NFR-05-01): how unit price ranges are estimated."""

    @abstractmethod
    def estimate(self, requests: list[PriceRequest]) -> dict[UUID, PriceEstimate]:
        """Estimates for the products it can price, in one go (one AI call, not one per line).
        Products left out have no estimate: "Precio por confirmar"."""


@dataclass(frozen=True, slots=True)
class DispatchLeadTime:
    """A dispatched product line: approved on one date, really dispatched on another."""

    product_id: UUID
    quantity: int
    approved_on: date
    dispatched_on: date


class DispatchSamples(ABC):
    """Real dispatches of the past (reconciled work orders), for the median of FR-02-06."""

    @abstractmethod
    def lead_times(
        self, product_ids: list[UUID], dispatched_since: date
    ) -> list[DispatchLeadTime]: ...


class DispatchDateEstimator(ABC):
    """Strategy (NFR-05-01): suggested dispatch date from historical medians (FR-02-06)."""

    @abstractmethod
    def suggest(self, items: list[tuple[UUID, int]], today: date) -> date | None:
        """``None`` = "Sin datos históricos suficientes para estimar la fecha de despacho"."""


class QuotationDocumentGenerator(ABC):
    @abstractmethod
    def preliminary_pdf(self, quotation: Quotation) -> bytes: ...

    @abstractmethod
    def formal_pdf(self, quotation: Quotation) -> bytes:
        """The official quotation with final prices (FR-02-13)."""
