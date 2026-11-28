"""Siigo export queue use cases (implements ``ExportQueue`` and ``ExportQueueFeed``).

The flat file and the move to "Registrada en Siigo" arrive in step 5d.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.accounting_export.domain.queue_entry import QueueEntry
from modules.accounting_export.ports.inbound.export_queue import (
    ExportQueue,
    ExportQueueFeed,
    QueueEntryView,
    QueueFilters,
    QueueItemView,
    SyncResult,
)
from modules.accounting_export.ports.outbound.ports import (
    QueuedWorkOrders,
    QueueRepository,
    WorkOrderSearch,
)
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission


class ExportQueueService(ExportQueue, ExportQueueFeed):
    def __init__(
        self,
        repository: QueueRepository,
        work_orders: QueuedWorkOrders,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._work_orders = work_orders
        self._now = clock

    # --- Screen -------------------------------------------------------------------------------

    def list_pending(
        self, actor: Actor, filters: QueueFilters, page_request: PageRequest
    ) -> Page[QueueEntryView]:
        actor.require(Permission.EXPORT_QUEUE_MANAGE)
        if (
            filters.created_from
            and filters.created_to
            and filters.created_from > filters.created_to
        ):
            raise ValidationError.for_field(
                "created_to", "La fecha final no puede ser anterior a la inicial."
            )
        pending = self._repository.pending()
        page = self._work_orders.search_among(
            frozenset(pending),
            WorkOrderSearch(
                filters.created_from, filters.created_to, filters.customer, filters.number
            ),
            page_request,
        )
        views = [
            QueueEntryView(
                work_order_id=o.id,
                number=o.number,
                quotation_number=o.quotation_number,
                created_at=o.created_at,
                enqueued_at=pending[o.id].enqueued_at,
                customer_tax_id=o.customer_tax_id,
                customer_name=o.customer_name,
                items=tuple(
                    QueueItemView(i.product_code, i.description, i.unit_of_measure, i.quantity)
                    for i in o.items
                ),
                agreed_delivery_date=o.agreed_delivery_date,
            )
            for o in page.items
        ]
        return Page(views, page.total, page.request)

    # --- Feed (events and the sync command) ---------------------------------------------------

    def enqueue(self, work_order_id: UUID) -> None:
        self._repository.add(QueueEntry.enqueue(work_order_id, self._now()))

    def withdraw(self, work_order_id: UUID) -> None:
        entry = self._repository.for_work_order(work_order_id)
        if entry is not None and entry.withdraw(self._now()):
            self._repository.update(entry)

    def sync(self) -> SyncResult:
        pending_orders = self._work_orders.pending_ids()
        queued = self._repository.pending()
        enqueued = sum(
            self._repository.add(QueueEntry.enqueue(work_order_id, self._now()))
            for work_order_id in pending_orders - set(queued)
        )
        withdrawn = 0
        for work_order_id, entry in queued.items():
            if work_order_id not in pending_orders and entry.withdraw(self._now()):
                self._repository.update(entry)
                withdrawn += 1
        return SyncResult(enqueued, withdrawn)
