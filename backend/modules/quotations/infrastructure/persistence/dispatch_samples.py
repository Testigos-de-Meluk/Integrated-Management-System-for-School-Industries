"""``DispatchSamples`` adapter: asks the work orders module through its inbound port."""

from datetime import date
from uuid import UUID

from modules.quotations.ports.outbound.ports import DispatchLeadTime, DispatchSamples
from modules.work_orders.ports.inbound.work_order_history import DispatchHistory


class WorkOrderDispatchSamples(DispatchSamples):
    def __init__(self, history: DispatchHistory) -> None:
        self._history = history

    def lead_times(self, product_ids: list[UUID], dispatched_since: date) -> list[DispatchLeadTime]:
        return [
            DispatchLeadTime(s.product_id, s.quantity, s.approved_on, s.dispatched_on)
            for s in self._history.samples(product_ids, dispatched_since)
        ]
