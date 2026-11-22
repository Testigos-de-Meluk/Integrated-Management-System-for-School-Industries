"""Inbound port used by the PUBLIC virtual assistant (no account, no Actor): FR-02-05, US 2.7 …
US 2.10. Only DTOs with plain values cross this boundary; prices travel as strings (whole pesos).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RequestedItem:
    product_id: UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class RequestQuotationCommand:
    full_name: str
    email: str
    phone: str
    items: tuple[RequestedItem, ...]
    data_consent: bool  # Law 1581 of 2012: authorization to process personal data
    institution: str | None = None
    tax_id: str | None = None


@dataclass(frozen=True, slots=True)
class EstimatedItemView:
    product_id: UUID
    product_code: str
    description: str
    unit_of_measure: str
    quantity: int
    unit_price_min: str | None  # None = "Precio por confirmar"
    unit_price_max: str | None
    subtotal_min: str | None
    subtotal_max: str | None


@dataclass(frozen=True, slots=True)
class EstimateView:
    """Live estimate while the requester chooses products (nothing is saved)."""

    items: tuple[EstimatedItemView, ...]
    total_min: str | None
    total_max: str | None
    unpriced_items: int


@dataclass(frozen=True, slots=True)
class PreliminaryQuotationView:
    id: UUID
    number: str
    issued_at: datetime
    valid_until: date
    requester_name: str
    requester_email: str
    items: tuple[EstimatedItemView, ...]
    total_min: str | None
    total_max: str | None
    unpriced_items: int
    estimated_dispatch_date: date | None  # None = to be confirmed by the company
    access_key: str  # needed to download or email this quotation


@dataclass(frozen=True, slots=True)
class QuotationDocument:
    filename: str
    content: bytes


class QuotationRequests(ABC):
    @abstractmethod
    def estimate(self, items: tuple[RequestedItem, ...]) -> EstimateView: ...

    @abstractmethod
    def request_quotation(
        self, command: RequestQuotationCommand, source_ip: str | None
    ) -> PreliminaryQuotationView:
        """Validates, estimates, saves it as "Pendiente de revisión" and returns it (US 2.10)."""

    @abstractmethod
    def document(self, quotation_id: UUID, access_key: str) -> QuotationDocument:
        """The preliminary quotation as a PDF (US 2.8)."""

    @abstractmethod
    def email_document(self, quotation_id: UUID, access_key: str) -> str:
        """Emails the PDF to the requester; returns the address it was sent to (US 2.9)."""
