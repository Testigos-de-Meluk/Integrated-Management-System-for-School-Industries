"""Outbound ports of the Accounting Export module."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from modules.accounting_export.domain.queue_entry import QueueEntry
from modules.shared_kernel.domain.pagination import Page, PageRequest


class QueueRepository(ABC):
    @abstractmethod
    def add(self, entry: QueueEntry) -> bool:
        """``False`` (and nothing saved) if the O.T. already has an entry: no duplicates."""

    @abstractmethod
    def update(self, entry: QueueEntry) -> None: ...

    @abstractmethod
    def for_work_order(self, work_order_id: UUID) -> QueueEntry | None: ...

    @abstractmethod
    def pending(self) -> dict[UUID, QueueEntry]:
        """PENDING_EXPORT entries by work order id."""


@dataclass(frozen=True, slots=True)
class QueuedLine:
    product_code: str
    description: str
    unit_of_measure: str
    quantity: int


@dataclass(frozen=True, slots=True)
class QueuedWorkOrder:
    """Plain data of one O.T. as the queue needs it."""

    id: UUID
    number: str
    quotation_number: str
    created_at: datetime
    customer_tax_id: str
    customer_name: str
    items: tuple[QueuedLine, ...]
    agreed_delivery_date: date


@dataclass(frozen=True, slots=True)
class WorkOrderSearch:
    created_from: date | None = None
    created_to: date | None = None
    customer: str | None = None
    number: str | None = None


class QueuedWorkOrders(ABC):
    """The O.T. data the queue shows, read from the work orders module."""

    @abstractmethod
    def search_among(
        self, work_order_ids: frozenset[UUID], search: WorkOrderSearch, page_request: PageRequest
    ) -> Page[QueuedWorkOrder]:
        """Oldest first."""

    @abstractmethod
    def pending_ids(self) -> frozenset[UUID]: ...
