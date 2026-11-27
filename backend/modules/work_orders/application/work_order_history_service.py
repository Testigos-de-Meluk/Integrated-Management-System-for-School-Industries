"""Implements the history ports other modules read (``DispatchHistory``, ``CustomerWorkOrders``)."""

from datetime import date
from uuid import UUID

from modules.shared_kernel.domain.document_numbers import business_date
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.work_orders.ports.inbound.work_order_history import (
    CustomerWorkOrders,
    CustomerWorkOrderView,
    DispatchHistory,
    DispatchSample,
)
from modules.work_orders.ports.outbound.ports import WorkOrderRepository


class WorkOrderHistoryService(DispatchHistory, CustomerWorkOrders):
    def __init__(self, repository: WorkOrderRepository) -> None:
        self._repository = repository

    def samples(self, product_ids: list[UUID], dispatched_since: date) -> list[DispatchSample]:
        if not product_ids:
            return []
        wanted = set(product_ids)
        samples = []
        for order in self._repository.reconciled_since(dispatched_since, product_ids):
            if order.quotation_approved_at is None or order.actual_dispatch_date is None:
                continue  # generated before step 5b: no approval date to measure from
            approved_on = business_date(order.quotation_approved_at)
            samples.extend(
                DispatchSample(
                    item.product_id, item.quantity, approved_on, order.actual_dispatch_date
                )
                for item in order.items
                if item.product_id in wanted
            )
        return samples

    def work_orders_of(
        self, customer_id: UUID, page_request: PageRequest
    ) -> Page[CustomerWorkOrderView]:
        page = self._repository.for_customer(customer_id, page_request)
        views = [
            CustomerWorkOrderView(
                o.id,
                o.number,
                o.quotation_number,
                o.created_at,
                o.agreed_delivery_date,
                o.status.value,
            )
            for o in page.items
        ]
        return Page(views, page.total, page.request)
