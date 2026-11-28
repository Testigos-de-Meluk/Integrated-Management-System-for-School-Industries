"""Outbound ports of the Accounting Export module."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from modules.accounting_export.domain.export_batch import ExportBatch
from modules.accounting_export.domain.queue_entry import QueueEntry
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor


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

    @abstractmethod
    def lock_for(self, work_order_ids: frozenset[UUID]) -> dict[UUID, QueueEntry]:
        """The entries of these O.T.s (any status) by work order id, locked until the end of the
        transaction."""

    @abstractmethod
    def work_orders_of_batches(self, batch_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        """The work order ids exported in each batch."""


@dataclass(frozen=True, slots=True)
class StoredFile:
    file_name: str
    content_type: str
    content: bytes


class BatchRepository(ABC):
    @abstractmethod
    def add(self, batch: ExportBatch, file: StoredFile) -> None: ...

    @abstractmethod
    def latest(self, page_request: PageRequest) -> Page[ExportBatch]:
        """Newest first."""

    @abstractmethod
    def file_of(self, batch_id: UUID) -> StoredFile | None: ...


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
    status: str = "PENDING"  # current WorkOrderStatus value


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

    @abstractmethod
    def views_of(self, work_order_ids: frozenset[UUID]) -> list[QueuedWorkOrder]:
        """Any status, oldest first (the O.T.s of a batch)."""

    @abstractmethod
    def register_exported(
        self, actor: Actor, work_order_ids: frozenset[UUID]
    ) -> list[QueuedWorkOrder]:
        """Moves them to "Registrada en Odoo" (all or nothing, 409 naming the O.T.s that are no
        longer "Pendiente"); oldest first."""


class OrderFileFormatter(ABC):
    """Strategy (NFR-05-01): the layout of the file the accounting system imports. Today the Odoo
    sale order import (.xlsx); another accounting system only needs another formatter."""

    extension: str
    content_type: str

    @abstractmethod
    def format(self, orders: list[QueuedWorkOrder]) -> bytes: ...
