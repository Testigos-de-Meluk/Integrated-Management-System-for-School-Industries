"""Inbound port of the quotation review (Administrador): US 2.12, US 2.13, US 2.25 … US 2.29.

Every use case requires ``QUOTATION_MANAGE``. Only DTOs with plain values cross this boundary;
money travels as strings of whole pesos.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from modules.quotations.domain.quotation import (
    MAX_ITEMS,
    MAX_QUANTITY,
    REASON_MAX_LENGTH,
    TERMS_MAX_LENGTH,
    QuotationStatus,
)
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor

#: Published for adapters, so they validate the same limits without importing the domain.
QUOTATION_STATUSES: tuple[str, ...] = tuple(s.value for s in QuotationStatus)
__all__ = [
    "MAX_ITEMS",
    "MAX_QUANTITY",
    "QUOTATION_STATUSES",
    "REASON_MAX_LENGTH",
    "TERMS_MAX_LENGTH",
    "ApproveQuotationCommand",
    "ItemPrice",
    "LinkedCustomerView",
    "ModifyQuotationCommand",
    "QuotationDetailView",
    "QuotationFilters",
    "QuotationReview",
    "QuotationSummaryView",
    "ReviewItemView",
    "ReviewedItem",
]

# --- Input DTOs -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QuotationFilters:
    """All optional, combined with AND (US 2.26)."""

    issued_from: date | None = None
    issued_to: date | None = None
    contact: str | None = None  # name, email, phone, institution or NIT of the requester
    product: str | None = None  # code or description of a quoted product
    total_min: Decimal | None = None
    total_max: Decimal | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewedItem:
    product_id: UUID
    quantity: int
    final_unit_price: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ModifyQuotationCommand:
    items: tuple[ReviewedItem, ...]
    reason: str  # why it was modified: kept in the audit log (US 2.28.7)
    commercial_terms: str | None = None
    dispatch_date: date | None = None


@dataclass(frozen=True, slots=True)
class ItemPrice:
    item_id: UUID
    final_unit_price: Decimal | None


@dataclass(frozen=True, slots=True)
class ApproveQuotationCommand:
    prices: tuple[ItemPrice, ...]
    dispatch_date: date | None
    commercial_terms: str | None = None


# --- Output DTOs ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LinkedCustomerView:
    id: UUID
    tax_id: str
    name: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class QuotationSummaryView:
    """One row of the review tray (US 2.25.2)."""

    id: UUID
    number: str
    issued_at: datetime
    status: str
    requester_name: str
    requester_email: str
    requester_phone: str
    requester_institution: str
    products: tuple[str, ...]  # descriptions, in order
    total_min: str | None
    total_max: str | None
    final_total: str | None
    unpriced_items: int
    has_customer: bool


@dataclass(frozen=True, slots=True)
class ReviewItemView:
    id: UUID
    product_id: UUID
    product_code: str
    description: str
    unit_of_measure: str
    quantity: int
    unit_price_min: str | None
    unit_price_max: str | None
    subtotal_min: str | None
    subtotal_max: str | None
    final_unit_price: str | None
    final_subtotal: str | None
    price_source: str | None  # "HISTORY" | "AI": where the estimated range came from


@dataclass(frozen=True, slots=True)
class QuotationDetailView:
    id: UUID
    number: str
    issued_at: datetime
    valid_until: date
    status: str
    is_editable: bool
    requester_name: str
    requester_email: str
    requester_phone: str
    requester_institution: str
    requester_tax_id: str
    items: tuple[ReviewItemView, ...]
    total_min: str | None
    total_max: str | None
    final_total: str | None
    unpriced_items: int
    estimated_dispatch_date: date | None
    dispatch_date_source: str | None  # "SUGGESTED" | "MANUAL"
    commercial_terms: str
    rejection_reason: str
    approved_at: datetime | None
    approved_by_name: str
    customer: LinkedCustomerView | None
    #: A registered customer whose NIT matches the one typed by the requester (not linked yet).
    suggested_customer: LinkedCustomerView | None
    #: The median recalculated now (FR-02-06); ``None`` when not editable or without enough
    #: history ("Sin datos históricos suficientes para estimar la fecha de despacho").
    suggested_dispatch_date: date | None = None


@dataclass(frozen=True, slots=True)
class QuotationFile:
    filename: str
    content: bytes


# --- Port -------------------------------------------------------------------------------------


class QuotationReview(ABC):
    @abstractmethod
    def list_quotations(
        self, actor: Actor, filters: QuotationFilters, page_request: PageRequest
    ) -> Page[QuotationSummaryView]:
        """Newest first (US 2.25, US 2.26)."""

    @abstractmethod
    def get_quotation(self, actor: Actor, quotation_id: UUID) -> QuotationDetailView: ...

    @abstractmethod
    def modify_quotation(
        self, actor: Actor, quotation_id: UUID, command: ModifyQuotationCommand
    ) -> QuotationDetailView:
        """→ "Modificada" (US 2.28). New products must be active in the catalog."""

    @abstractmethod
    def approve_quotation(
        self, actor: Actor, quotation_id: UUID, command: ApproveQuotationCommand
    ) -> QuotationDetailView:
        """→ "Aprobada": emails the formal PDF and publishes ``QuotationApproved`` (US 2.27)."""

    @abstractmethod
    def reject_quotation(
        self, actor: Actor, quotation_id: UUID, reason: str
    ) -> QuotationDetailView:
        """→ "Rechazada": emails the reason to the requester (US 2.29)."""

    @abstractmethod
    def link_customer(
        self, actor: Actor, quotation_id: UUID, customer_id: UUID | None
    ) -> QuotationDetailView:
        """Links an ACTIVE registered customer (or unlinks it with ``None`` while in review)."""

    @abstractmethod
    def document(self, actor: Actor, quotation_id: UUID) -> QuotationFile:
        """The formal PDF once approved; the preliminary one before."""
