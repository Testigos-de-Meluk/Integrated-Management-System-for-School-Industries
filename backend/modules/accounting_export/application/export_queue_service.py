"""Odoo export queue use cases (implements ``ExportQueue`` and ``ExportQueueFeed``).

Exporting (step 5d) builds the file with the ``OrderFileFormatter`` Strategy, moves the O.T.s to
"Registrada en Odoo" through the work orders inbound port and stores the batch with its file.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.accounting_export.domain.export_batch import ExportBatch, validate_selection
from modules.accounting_export.domain.queue_entry import QueueEntry
from modules.accounting_export.ports.inbound.export_queue import (
    BatchFileView,
    BatchWorkOrderView,
    ExportBatchView,
    ExportQueue,
    ExportQueueFeed,
    QueueEntryView,
    QueueFilters,
    QueueItemView,
    SyncResult,
)
from modules.accounting_export.ports.outbound.ports import (
    BatchRepository,
    OrderFileFormatter,
    QueuedWorkOrder,
    QueuedWorkOrders,
    QueueRepository,
    StoredFile,
    WorkOrderSearch,
)
from modules.shared_kernel.domain.audit import AuditAction, AuditRecord
from modules.shared_kernel.domain.exceptions import ConflictError, NotFoundError, ValidationError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger

CANCELLED = "CANCELLED"


class BatchNotFound(NotFoundError):
    default_message = "El lote de exportación no existe."


class QueueOutOfSync(ConflictError):
    """An O.T. that is still "Pendiente" has no pending queue entry (should never happen)."""

    code = "EXPORT_QUEUE_OUT_OF_SYNC"

    def __init__(self, numbers: list[str]) -> None:
        super().__init__(
            "Estas órdenes de trabajo no están en la cola de exportación: "
            f"{', '.join(numbers)}. Actualice la lista y vuelva a intentarlo."
        )


class ExportQueueService(ExportQueue, ExportQueueFeed):
    def __init__(
        self,
        repository: QueueRepository,
        work_orders: QueuedWorkOrders,
        *,
        batches: BatchRepository | None = None,
        formatter: OrderFileFormatter | None = None,
        audit_logger: AuditLogger | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._work_orders = work_orders
        self._batches = batches
        self._formatter = formatter
        self._audit = audit_logger
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

    # --- Export batches (step 5d) --------------------------------------------------------------

    def export(self, actor: Actor, work_order_ids: frozenset[UUID]) -> ExportBatchView:
        actor.require(Permission.EXPORT_QUEUE_MANAGE)
        validate_selection(work_order_ids)
        # Work orders first (locked there), then the queue: the same order as annulling an O.T.,
        # so an export and an annulment of the same O.T. wait for each other instead of
        # deadlocking. A second export of the same O.T. waits and then gets the 409.
        orders = self._work_orders.register_exported(actor, work_order_ids)
        entries = self._repository.lock_for(work_order_ids)
        missing = [o.number for o in orders if not (e := entries.get(o.id)) or not e.is_pending]
        if missing:
            raise QueueOutOfSync(missing)

        now = self._now()
        batch = ExportBatch.generate(
            work_order_numbers=tuple(o.number for o in orders),
            extension=self._formatter.extension,
            now=now,
            by_id=actor.user_id,
            by_name=actor.display_name or actor.role.value,
        )
        content = self._formatter.format(orders)
        self._batches.add(batch, StoredFile(batch.file_name, self._formatter.content_type, content))
        for order in orders:
            entry = entries[order.id]
            entry.mark_exported(batch.id, now)
            self._repository.update(entry)
        self._audit.log(
            AuditRecord(
                action=AuditAction.EXPORTED,
                entity_type="ExportBatch",
                entity_id=str(batch.id),
                actor=actor,
                new_values={
                    "file_name": batch.file_name,
                    "work_orders": list(batch.work_order_numbers),
                },
            )
        )
        return self._batch_view(batch, orders)

    def list_batches(self, actor: Actor, page_request: PageRequest) -> Page[ExportBatchView]:
        actor.require(Permission.EXPORT_QUEUE_MANAGE)
        page = self._batches.latest(page_request)
        ids_by_batch = self._repository.work_orders_of_batches([b.id for b in page.items])
        all_ids = frozenset(i for ids in ids_by_batch.values() for i in ids)
        orders = {o.id: o for o in self._work_orders.views_of(all_ids)}
        views = [
            self._batch_view(
                batch, [orders[i] for i in ids_by_batch.get(batch.id, []) if i in orders]
            )
            for batch in page.items
        ]
        return Page(views, page.total, page.request)

    def batch_file(self, actor: Actor, batch_id: UUID) -> BatchFileView:
        actor.require(Permission.EXPORT_QUEUE_MANAGE)
        stored = self._batches.file_of(batch_id)
        if stored is None:
            raise BatchNotFound()
        return BatchFileView(stored.file_name, stored.content_type, stored.content)

    @staticmethod
    def _batch_view(batch: ExportBatch, orders: list[QueuedWorkOrder]) -> ExportBatchView:
        ordered = sorted(orders, key=lambda o: (o.created_at, o.number))
        return ExportBatchView(
            id=batch.id,
            file_name=batch.file_name,
            created_at=batch.created_at,
            created_by_name=batch.created_by_name,
            work_orders=tuple(
                BatchWorkOrderView(
                    work_order_id=o.id,
                    number=o.number,
                    customer_name=o.customer_name,
                    status=o.status,
                    cancelled_after_export=o.status == CANCELLED,
                )
                for o in ordered
            ),
        )

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
