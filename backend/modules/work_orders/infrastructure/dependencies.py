"""Composition root of the Work Orders module."""

from functools import lru_cache

from modules.customers.infrastructure.dependencies import customer_directory
from modules.products.infrastructure.dependencies import product_catalog
from modules.quotations.infrastructure.dependencies import approved_quotations
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger
from modules.shared_kernel.infrastructure.events.in_process_event_bus import event_bus
from modules.work_orders.application.work_order_history_service import WorkOrderHistoryService
from modules.work_orders.application.work_order_service import WorkOrderService
from modules.work_orders.ports.inbound.exportable_work_orders import ExportableWorkOrders
from modules.work_orders.ports.inbound.work_order_history import (
    CustomerWorkOrders,
    DispatchHistory,
)
from modules.work_orders.ports.inbound.work_order_management import WorkOrderManagement

from .persistence.repositories import DjangoWorkOrderNumberGenerator, DjangoWorkOrderRepository


@lru_cache(maxsize=1)
def work_order_history() -> WorkOrderHistoryService:
    """For other modules: dispatch samples (quotations) and a customer's O.T.s (customers)."""
    return WorkOrderHistoryService(DjangoWorkOrderRepository())


def dispatch_history() -> DispatchHistory:
    return work_order_history()


def customer_work_orders() -> CustomerWorkOrders:
    return work_order_history()


def exportable_work_orders() -> ExportableWorkOrders:
    """For the accounting export module (Siigo queue)."""
    return work_order_history()


@lru_cache(maxsize=1)
def work_order_management() -> WorkOrderManagement:
    return WorkOrderService(
        repository=DjangoWorkOrderRepository(),
        numbers=DjangoWorkOrderNumberGenerator(),
        quotations=approved_quotations(),  # inbound port of the quotations module
        customers=customer_directory(),  # inbound port of the customers module
        catalog=product_catalog(),  # inbound port of the products module
        events=event_bus,
        audit_logger=DatabaseAuditLogger(),
    )
