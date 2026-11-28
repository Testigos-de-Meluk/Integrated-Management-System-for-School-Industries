"""Composition root of the Accounting Export module."""

from functools import lru_cache

from modules.accounting_export.application.export_queue_service import ExportQueueService
from modules.accounting_export.ports.inbound.export_queue import ExportQueue, ExportQueueFeed
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger
from modules.work_orders.infrastructure.dependencies import exportable_work_orders

from .files.odoo_sale_orders import OdooSaleOrderXlsxFormatter
from .persistence.repositories import (
    DjangoBatchRepository,
    DjangoQueueRepository,
    WorkOrdersForQueue,
)


@lru_cache(maxsize=1)
def export_queue_service() -> ExportQueueService:
    return ExportQueueService(
        DjangoQueueRepository(),
        WorkOrdersForQueue(exportable_work_orders()),  # inbound port of the work orders module
        batches=DjangoBatchRepository(),
        formatter=OdooSaleOrderXlsxFormatter(),  # Strategy: the accounting system's layout
        audit_logger=DatabaseAuditLogger(),
    )


def export_queue() -> ExportQueue:
    """The "Exportación a Odoo" screen."""
    return export_queue_service()


def export_queue_feed() -> ExportQueueFeed:
    """Work order events and the ``sync_export_queue`` command."""
    return export_queue_service()
