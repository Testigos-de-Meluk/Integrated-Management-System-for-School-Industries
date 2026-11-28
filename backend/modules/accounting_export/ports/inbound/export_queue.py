"""Inbound ports of the Siigo export queue.

* ``ExportQueue``: the "Exportación a Siigo" screen (US 2.31 … US 2.33), ``EXPORT_QUEUE_MANAGE``.
* ``ExportQueueFeed``: fed by work order events and by the ``sync_export_queue`` command (system,
  no ``Actor``).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor


@dataclass(frozen=True, slots=True)
class QueueFilters:
    """All optional, combined with AND (US 2.32). Dates are the O.T. generation date."""

    created_from: date | None = None
    created_to: date | None = None
    customer: str | None = None  # name or tax id
    number: str | None = None  # O.T. number


@dataclass(frozen=True, slots=True)
class QueueItemView:
    product_code: str
    description: str
    unit_of_measure: str
    quantity: int


@dataclass(frozen=True, slots=True)
class QueueEntryView:
    """Current data of a queued O.T. (read live from the work orders module)."""

    work_order_id: UUID
    number: str
    quotation_number: str
    created_at: datetime
    enqueued_at: datetime
    customer_tax_id: str
    customer_name: str
    items: tuple[QueueItemView, ...]
    agreed_delivery_date: date


class ExportQueue(ABC):
    @abstractmethod
    def list_pending(
        self, actor: Actor, filters: QueueFilters, page_request: PageRequest
    ) -> Page[QueueEntryView]:
        """O.T.s waiting to be exported, oldest first (US 2.31, US 2.32)."""


@dataclass(frozen=True, slots=True)
class SyncResult:
    enqueued: int
    withdrawn: int


class ExportQueueFeed(ABC):
    @abstractmethod
    def enqueue(self, work_order_id: UUID) -> None:
        """A generated O.T. enters the queue once (US 2.30.4: no duplicates)."""

    @abstractmethod
    def withdraw(self, work_order_id: UUID) -> None:
        """An annulled O.T. leaves the queue if it was not exported yet."""

    @abstractmethod
    def sync(self) -> SyncResult:
        """Rebuilds the queue from the PENDING O.T.s: enqueues the missing ones and withdraws
        pending entries whose O.T. is no longer pending. Safe to run more than once."""
