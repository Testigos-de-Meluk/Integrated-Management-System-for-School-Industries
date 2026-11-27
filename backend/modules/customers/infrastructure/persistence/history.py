"""``CommercialHistoryProvider`` adapter: asks the quotations and work orders modules through
their inbound ports (one paginated list per document type, step 5b decision)."""

from uuid import UUID

from modules.customers.ports.outbound.repositories import CommercialHistoryProvider, HistoryEntry
from modules.quotations.ports.inbound.customer_quotations import CustomerQuotations
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.work_orders.ports.inbound.work_order_history import CustomerWorkOrders


class ModulesCommercialHistory(CommercialHistoryProvider):
    def __init__(self, quotations: CustomerQuotations, work_orders: CustomerWorkOrders) -> None:
        self._quotations = quotations
        self._work_orders = work_orders

    def history_for(
        self, customer_id: UUID, document_type: str, page_request: PageRequest
    ) -> Page[HistoryEntry]:
        if document_type == "WORK_ORDER":
            orders = self._work_orders.work_orders_of(customer_id, page_request)
            entries = [
                HistoryEntry(o.id, "WORK_ORDER", o.number, o.created_at, o.status)
                for o in orders.items
            ]
            return Page(entries, orders.total, orders.request)
        page = self._quotations.quotations_of(customer_id, page_request)
        entries = [
            HistoryEntry(q.id, "QUOTATION", q.number, q.issued_at, q.status) for q in page.items
        ]
        return Page(entries, page.total, page.request)
