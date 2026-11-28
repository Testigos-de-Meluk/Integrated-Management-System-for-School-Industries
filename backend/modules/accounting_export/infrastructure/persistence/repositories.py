"""PostgreSQL adapter of the export queue, and the adapter that reads O.T.s from work orders."""

from uuid import UUID

from django.db import IntegrityError, transaction

from modules.accounting_export.domain.queue_entry import QueueEntry, QueueStatus
from modules.accounting_export.infrastructure.models import QueueEntryModel
from modules.accounting_export.ports.outbound.ports import (
    QueuedLine,
    QueuedWorkOrder,
    QueuedWorkOrders,
    QueueRepository,
    WorkOrderSearch,
)
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.work_orders.ports.inbound.exportable_work_orders import (
    ExportableWorkOrders,
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
        orders = [
            QueuedWorkOrder(
                id=o.id,
                number=o.number,
                quotation_number=o.quotation_number,
                created_at=o.created_at,
                customer_tax_id=o.customer_tax_id,
                customer_name=o.customer_name,
                items=tuple(
                    QueuedLine(i.product_code, i.description, i.unit_of_measure, i.quantity)
                    for i in o.items
                ),
                agreed_delivery_date=o.agreed_delivery_date,
            )
            for o in page.items
        ]
        return Page(orders, page.total, page.request)

    def pending_ids(self) -> frozenset[UUID]:
        return self._work_orders.pending_ids()
