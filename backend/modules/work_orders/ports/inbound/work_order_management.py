"""Inbound port of the work orders screen: US 2.35 … US 2.40 (corrected in step 5).

Every use case requires ``WORK_ORDER_MANAGE`` (Operador, Administrador, Superadministrador). Only
DTOs with plain values cross this boundary.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor
from modules.work_orders.domain.work_order import (
    MAX_ITEMS,
    MAX_QUANTITY,
    REASON_MAX_LENGTH,
    WorkOrderStatus,
)

#: Published for adapters, so they validate the same limits without importing the domain.
WORK_ORDER_STATUSES: tuple[str, ...] = tuple(s.value for s in WorkOrderStatus)
__all__ = [
    "MAX_ITEMS",
    "MAX_QUANTITY",
    "REASON_MAX_LENGTH",
    "WORK_ORDER_STATUSES",
]

# --- Input DTOs -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkOrderFilters:
    """All optional, combined with AND (US 2.36)."""

    number: str | None = None
    quotation_number: str | None = None
    customer: str | None = None  # name or tax id
    product: str | None = None  # code or description
    agreed_from: date | None = None
    agreed_to: date | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class WorkOrderItemInput:
    product_id: UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class GenerateWorkOrderCommand:
    quotation_id: UUID
    #: Required only when the quotation has no customer: it is linked to the quotation too.
    customer_id: UUID | None = None
    #: Defaults to the quotation's dispatch date (if it is not in the past).
    agreed_delivery_date: date | None = None


@dataclass(frozen=True, slots=True)
class UpdateWorkOrderCommand:
    customer_id: UUID
    items: tuple[WorkOrderItemInput, ...]
    agreed_delivery_date: date


# --- Output DTOs ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkOrderItemView:
    product_id: UUID
    product_code: str
    description: str
    unit_of_measure: str
    quantity: int


@dataclass(frozen=True, slots=True)
class WorkOrderSummaryView:
    id: UUID
    number: str
    quotation_id: UUID
    quotation_number: str
    customer_id: UUID
    customer_tax_id: str
    customer_name: str
    items: tuple[WorkOrderItemView, ...]
    agreed_delivery_date: date
    status: str  # WorkOrderStatus value
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WorkOrderDetailView:
    id: UUID
    number: str
    quotation_id: UUID
    quotation_number: str
    customer_id: UUID
    customer_tax_id: str
    customer_name: str
    items: tuple[WorkOrderItemView, ...]
    agreed_delivery_date: date
    actual_dispatch_date: date | None
    status: str
    cancellation_reason: str
    created_at: datetime
    created_by_name: str
    can_edit: bool
    can_reconcile: bool
    can_cancel: bool
    was_exported: bool  # annulling it needs the "also annul it in Odoo" warning


@dataclass(frozen=True, slots=True)
class AvailableQuotationView:
    """An approved quotation without an active O.T. (the "Generar O.T." list)."""

    id: UUID
    number: str
    approved_at: datetime
    requester_name: str
    requester_institution: str
    requester_tax_id: str
    customer_id: UUID | None
    customer_name: str | None
    customer_active: bool | None
    dispatch_date: date | None
    items: tuple[WorkOrderItemView, ...]


class WorkOrderManagement(ABC):
    @abstractmethod
    def list_work_orders(
        self, actor: Actor, filters: WorkOrderFilters, page_request: PageRequest
    ) -> Page[WorkOrderSummaryView]:
        """Newest first (US 2.35, US 2.36)."""

    @abstractmethod
    def get_work_order(self, actor: Actor, work_order_id: UUID) -> WorkOrderDetailView: ...

    @abstractmethod
    def available_quotations(
        self, actor: Actor, text: str | None, page_request: PageRequest
    ) -> Page[AvailableQuotationView]:
        """Approved quotations that can generate an O.T. (none active)."""

    @abstractmethod
    def generate(self, actor: Actor, command: GenerateWorkOrderCommand) -> WorkOrderDetailView:
        """FR-02-20 / US 2.37: "Pendiente", enters the export queue, audited."""

    @abstractmethod
    def update(
        self, actor: Actor, work_order_id: UUID, command: UpdateWorkOrderCommand
    ) -> WorkOrderDetailView:
        """FR-02-21 / US 2.38: only while "Pendiente"."""

    @abstractmethod
    def cancel(self, actor: Actor, work_order_id: UUID, reason: str) -> WorkOrderDetailView:
        """FR-02-22 / US 2.39: any status except "Anulada", with a reason."""

    @abstractmethod
    def reconcile(
        self, actor: Actor, work_order_id: UUID, actual_dispatch_date: date
    ) -> WorkOrderDetailView:
        """US 2.40: "Registrada en Odoo" → "Conciliada" with the real dispatch date."""
