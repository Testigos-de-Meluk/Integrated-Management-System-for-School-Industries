"""PostgreSQL adapter of the export queue, and the adapter that reads O.T.s from work orders."""

from uuid import UUID

from django.db import IntegrityError, transaction

from modules.accounting_export.domain.export_batch import ExportBatch
from modules.accounting_export.domain.queue_entry import QueueEntry, QueueStatus
from modules.accounting_export.infrastructure.models import ExportBatchModel, QueueEntryModel
from modules.accounting_export.ports.outbound.ports import (
    BatchRepository,
    QueuedLine,
    QueuedWorkOrder,
    QueuedWorkOrders,
    QueueRepository,
    StoredFile,
    WorkOrderSearch,
)
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor
from modules.work_orders.ports.inbound.exportable_work_orders import (
    ExportableWorkOrders,
    ExportableWorkOrderView,
    ExportFilters,
)


def _to_domain(model: QueueEntryModel) -> QueueEntry:
    return QueueEntry(
        id=model.id,
        work_order_id=model.work_order_id,
        enqueued_at=model.enqueued_at,
        status=QueueStatus(model.status),
        withdrawn_at=model.withdrawn_at,
        exported_at=model.exported_at,
        export_batch_id=model.export_batch_id,
    )


class DjangoQueueRepository(QueueRepository):
    def add(self, entry: QueueEntry) -> bool:
        try:
            with transaction.atomic():  # savepoint: a duplicate must not break the request
                QueueEntryModel.objects.create(
                    id=entry.id,
                    work_order_id=entry.work_order_id,
                    status=entry.status.value,
                    enqueued_at=entry.enqueued_at,
                )
        except IntegrityError:
            return False
        return True

    def update(self, entry: QueueEntry) -> None:
        QueueEntryModel.objects.filter(pk=entry.id).update(
            status=entry.status.value,
            withdrawn_at=entry.withdrawn_at,
            exported_at=entry.exported_at,
            export_batch_id=entry.export_batch_id,
        )

    def for_work_order(self, work_order_id: UUID) -> QueueEntry | None:
        model = QueueEntryModel.objects.filter(work_order_id=work_order_id).first()
        return _to_domain(model) if model else None

    def pending(self) -> dict[UUID, QueueEntry]:
        models = QueueEntryModel.objects.filter(status=QueueEntryModel.Status.PENDING_EXPORT)
        return {m.work_order_id: _to_domain(m) for m in models}

    def lock_for(self, work_order_ids: frozenset[UUID]) -> dict[UUID, QueueEntry]:
        models = (
            QueueEntryModel.objects.select_for_update()
            .filter(work_order_id__in=work_order_ids)
            .order_by("work_order_id")
        )
        return {m.work_order_id: _to_domain(m) for m in models}

    def work_orders_of_batches(self, batch_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {batch_id: [] for batch_id in batch_ids}
        rows = QueueEntryModel.objects.filter(export_batch_id__in=batch_ids).values_list(
            "export_batch_id", "work_order_id"
        )
        for batch_id, work_order_id in rows:
            result[batch_id].append(work_order_id)
        return result


def _batch_to_domain(model: ExportBatchModel) -> ExportBatch:
    return ExportBatch(
        id=model.id,
        file_name=model.file_name,
        created_at=model.created_at,
        created_by_id=model.created_by_id,
        created_by_name=model.created_by_name,
        work_order_numbers=(),  # read from the queue entries of the batch
    )


class DjangoBatchRepository(BatchRepository):
    def add(self, batch: ExportBatch, file: StoredFile) -> None:
        ExportBatchModel.objects.create(
            id=batch.id,
            file_name=file.file_name,
            content_type=file.content_type,
            content=file.content,
            created_at=batch.created_at,
            created_by_id=batch.created_by_id,
            created_by_name=batch.created_by_name,
        )

    def latest(self, page_request: PageRequest) -> Page[ExportBatch]:
        queryset = ExportBatchModel.objects.defer("content")
        total = queryset.count()
        start = page_request.offset
        models = queryset.order_by("-created_at")[start : start + page_request.size]
        return Page([_batch_to_domain(m) for m in models], total, page_request)

    def file_of(self, batch_id: UUID) -> StoredFile | None:
        model = ExportBatchModel.objects.filter(pk=batch_id).first()
        if model is None:
            return None
        return StoredFile(model.file_name, model.content_type, bytes(model.content))


def _queued(order: ExportableWorkOrderView) -> QueuedWorkOrder:
    return QueuedWorkOrder(
        id=order.id,
        number=order.number,
        quotation_number=order.quotation_number,
        created_at=order.created_at,
        customer_tax_id=order.customer_tax_id,
        customer_name=order.customer_name,
        items=tuple(
            QueuedLine(i.product_code, i.description, i.unit_of_measure, i.quantity)
            for i in order.items
        ),
        agreed_delivery_date=order.agreed_delivery_date,
        status=order.status,
    )


class WorkOrdersForQueue(QueuedWorkOrders):
    """Asks the work orders module through its inbound port."""

    def __init__(self, work_orders: ExportableWorkOrders) -> None:
        self._work_orders = work_orders

    def search_among(
        self, work_order_ids: frozenset[UUID], search: WorkOrderSearch, page_request: PageRequest
    ) -> Page[QueuedWorkOrder]:
        page = self._work_orders.search_among(
            work_order_ids,
            ExportFilters(search.created_from, search.created_to, search.customer, search.number),
            page_request,
        )
        return Page([_queued(o) for o in page.items], page.total, page.request)

    def pending_ids(self) -> frozenset[UUID]:
        return self._work_orders.pending_ids()

    def views_of(self, work_order_ids: frozenset[UUID]) -> list[QueuedWorkOrder]:
        return [_queued(o) for o in self._work_orders.views_of(work_order_ids)]

    def register_exported(
        self, actor: Actor, work_order_ids: frozenset[UUID]
    ) -> list[QueuedWorkOrder]:
        return [_queued(o) for o in self._work_orders.register_exported(actor, work_order_ids)]
