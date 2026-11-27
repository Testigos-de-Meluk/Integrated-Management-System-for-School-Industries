"""Inbound ports used by OTHER MODULES: what the work orders tell about the past.

* ``DispatchHistory`` → quotations: real dispatch samples for the suggested date (FR-02-06).
* ``CustomerWorkOrders`` → customers: the O.T.s of a customer for its 360 profile (US 2.20).

No ``Actor``: the calling module has already checked its own permission.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest


@dataclass(frozen=True, slots=True)
class DispatchSample:
    """One product line of a reconciled O.T. (never an annulled one)."""

    product_id: UUID
    quantity: int
    approved_on: date  # local date the source quotation was approved
    dispatched_on: date  # real dispatch date


class DispatchHistory(ABC):
    @abstractmethod
    def samples(self, product_ids: list[UUID], dispatched_since: date) -> list[DispatchSample]:
        """Lines of RECONCILED O.T.s with these products, dispatched on or after the date."""


@dataclass(frozen=True, slots=True)
class CustomerWorkOrderView:
    id: UUID
    number: str
    quotation_number: str
    created_at: datetime
    agreed_delivery_date: date
    status: str  # WorkOrderStatus value


class CustomerWorkOrders(ABC):
    @abstractmethod
    def work_orders_of(
        self, customer_id: UUID, page_request: PageRequest
    ) -> Page[CustomerWorkOrderView]:
        """Newest first."""
