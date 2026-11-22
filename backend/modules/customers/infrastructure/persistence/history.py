"""``CommercialHistoryProvider`` adapter: asks the quotations module through its inbound port.

Work orders (roadmap step 5) will be merged here, newest first, through their own inbound port.
"""

from uuid import UUID

from modules.customers.ports.outbound.repositories import CommercialHistoryProvider, HistoryEntry
from modules.quotations.ports.inbound.customer_quotations import CustomerQuotations
from modules.shared_kernel.domain.pagination import Page, PageRequest


class QuotationsCommercialHistory(CommercialHistoryProvider):
    def __init__(self, quotations: CustomerQuotations) -> None:
        self._quotations = quotations

    def history_for(self, customer_id: UUID, page_request: PageRequest) -> Page[HistoryEntry]:
        page = self._quotations.quotations_of(customer_id, page_request)
        entries = [HistoryEntry("QUOTATION", q.number, q.issued_at, q.status) for q in page.items]
        return Page(entries, page.total, page.request)
