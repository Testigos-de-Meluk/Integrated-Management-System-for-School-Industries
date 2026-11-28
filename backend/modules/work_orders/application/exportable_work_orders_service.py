"""Implements ``ExportableWorkOrders``: what the accounting export module reads and changes."""

from uuid import UUID

from modules.shared_kernel.domain.audit import AuditAction, AuditRecord
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger
from modules.work_orders.domain.exceptions import WorkOrdersNotPending
from modules.work_orders.domain.work_order import WorkOrder, WorkOrderStatus
from modules.work_orders.ports.inbound.exportable_work_orders import (
    ExportableItemView,
    ExportableWorkOrders,
    ExportableWorkOrderView,
    ExportFilters,
)
from modules.work_orders.ports.outbound.ports import WorkOrderRepository


def exportable_view(order: WorkOrder) -> ExportableWorkOrderView:
    return ExportableWorkOrderView(
        id=order.id,
        number=order.number,
        quotation_number=order.quotation_number,
        created_at=order.created_at,
        customer_tax_id=order.customer.tax_id,
        customer_name=order.customer.name,
        items=tuple(
            ExportableItemView(
                i.product_id, i.product_code, i.description, i.unit_of_measure, i.quantity
            )
            for i in order.items
        ),
        agreed_delivery_date=order.agreed_delivery_date,
        status=order.status.value,
    )


class ExportableWorkOrdersService(ExportableWorkOrders):
    def __init__(self, repository: WorkOrderRepository, audit_logger: AuditLogger) -> None:
        self._repository = repository
        self._audit = audit_logger

    def search_among(
        self, work_order_ids: frozenset[UUID], filters: ExportFilters, page_request: PageRequest
    ) -> Page[ExportableWorkOrderView]:
        if not work_order_ids:
            return Page([], 0, page_request)
        page = self._repository.search_among(work_order_ids, filters, page_request)
        return Page([exportable_view(o) for o in page.items], page.total, page.request)

    def pending_ids(self) -> frozenset[UUID]:
        return self._repository.pending_ids()

    def views_of(self, work_order_ids: frozenset[UUID]) -> list[ExportableWorkOrderView]:
        return [exportable_view(o) for o in self._repository.many(work_order_ids)]

    def register_exported(
        self, actor: Actor, work_order_ids: frozenset[UUID]
    ) -> list[ExportableWorkOrderView]:
        orders = self._repository.many(work_order_ids, lock=True)
        found = {o.id for o in orders}
        not_pending = [o.number for o in orders if o.status is not WorkOrderStatus.PENDING]
        if not_pending or found != work_order_ids:
            raise WorkOrdersNotPending(not_pending or ["(orden inexistente)"])
        for order in orders:
            before = order.snapshot()
            order.mark_registered_in_accounting()
            self._repository.update(order)
            self._audit.log(
                AuditRecord(
                    action=AuditAction.STATUS_CHANGED,
                    entity_type="WorkOrder",
                    entity_id=str(order.id),
                    actor=actor,
                    old_values=before,
                    new_values=order.snapshot(),
                    reason="Exportada a Odoo",
                )
            )
        return [exportable_view(o) for o in orders]
