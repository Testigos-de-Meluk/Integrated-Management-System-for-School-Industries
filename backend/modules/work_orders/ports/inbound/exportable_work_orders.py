"""Inbound port used by the ACCOUNTING EXPORT module (Odoo export queue, FR-02-16 … FR-02-18).

The queue only keeps which O.T.s are waiting and since when; it always shows the **current** data
of each O.T. through this port (step 5c decision). The queries take no ``Actor``: the export module
has already checked ``EXPORT_QUEUE_MANAGE``. ``register_exported`` does take it, because the status
change is audited here, in the module that owns the O.T.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor


@dataclass(frozen=True, slots=True)
class ExportFilters:
    """All optional, combined with AND (US 2.32)."""

    created_from: date | None = None
    created_to: date | None = None
    customer: str | None = None  # name or tax id
    number: str | None = None  # O.T. number


@dataclass(frozen=True, slots=True)
class ExportableItemView:
    product_id: UUID
    product_code: str
    description: str
    unit_of_measure: str
    quantity: int


@dataclass(frozen=True, slots=True)
class ExportableWorkOrderView:
    id: UUID
    number: str
    quotation_number: str
    created_at: datetime
    customer_tax_id: str
    customer_name: str
    items: tuple[ExportableItemView, ...]
    agreed_delivery_date: date
    status: str  # WorkOrderStatus value


class ExportableWorkOrders(ABC):
    @abstractmethod
    def search_among(
        self, work_order_ids: frozenset[UUID], filters: ExportFilters, page_request: PageRequest
    ) -> Page[ExportableWorkOrderView]:
        """The O.T.s among ``work_order_ids`` that match the filters, oldest first."""

    @abstractmethod
    def pending_ids(self) -> frozenset[UUID]:
        """Every PENDING O.T. (to rebuild the queue with ``sync_export_queue``)."""

    @abstractmethod
    def views_of(self, work_order_ids: frozenset[UUID]) -> list[ExportableWorkOrderView]:
        """The O.T.s among ``work_order_ids`` in any status (e.g. the O.T.s of a batch), oldest
        first. Unknown ids are skipped."""

    @abstractmethod
    def register_exported(
        self, actor: Actor, work_order_ids: frozenset[UUID]
    ) -> list[ExportableWorkOrderView]:
        """Moves every O.T. from "Pendiente" to "Registrada en Odoo" (FR-02-18, FR-02-23) and
        audits each change; returns them oldest first. All or nothing: raises
        ``WorkOrdersNotPending`` (409) naming the O.T.s that are no longer "Pendiente"."""
