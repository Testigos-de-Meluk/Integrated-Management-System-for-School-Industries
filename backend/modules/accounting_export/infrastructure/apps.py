from django.apps import AppConfig


class AccountingExportConfig(AppConfig):
    name = "modules.accounting_export.infrastructure"
    label = "accounting_export"
    verbose_name = "Accounting Export"

    def ready(self) -> None:
        """Subscribes to work order events (Observer pattern, NFR-05-01; FR-02-16).

        The in-process bus runs the handlers inside the request's transaction: if enqueueing
        fails, the O.T. generation is rolled back too, so no O.T. is ever left out of the queue.
        """
        from modules.shared_kernel.infrastructure.events.in_process_event_bus import event_bus
        from modules.work_orders.domain.events import WorkOrderCancelled, WorkOrderGenerated

        from .dependencies import export_queue_feed

        event_bus.subscribe(
            WorkOrderGenerated, lambda event: export_queue_feed().enqueue(event.work_order_id)
        )
        event_bus.subscribe(
            WorkOrderCancelled, lambda event: export_queue_feed().withdraw(event.work_order_id)
        )
