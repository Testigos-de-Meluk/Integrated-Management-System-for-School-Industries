"""Outbound ports of the Work Orders module."""

from abc import ABC, abstractmethod
from datetime import date, datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.work_orders.domain.work_order import WorkOrder
from modules.work_orders.ports.inbound.exportable_work_orders import ExportFilters
from modules.work_orders.ports.inbound.work_order_management import WorkOrderFilters


class WorkOrderRepository(ABC):
    @abstractmethod
    def add(self, work_order: WorkOrder) -> None:
        """Raises ``ActiveWorkOrderExists`` if the quotation already has an active O.T."""

    @abstractmethod
    def get(self, work_order_id: UUID) -> WorkOrder | None: ...

    @abstractmethod
    def update(self, work_order: WorkOrder) -> None:
        """Saves the header and replaces the items."""

    @abstractmethod
    def search(self, filters: WorkOrderFilters, page_request: PageRequest) -> Page[WorkOrder]:
        """One page matching every filter, newest first."""

    @abstractmethod
    def active_for_quotation(self, quotation_id: UUID) -> WorkOrder | None: ...

    @abstractmethod
    def quotations_with_active_order(self) -> frozenset[UUID]: ...

    @abstractmethod
    def reconciled_since(self, dispatched_since: date, product_ids: list[UUID]) -> list[WorkOrder]:
        """RECONCILED O.T.s dispatched on or after the date that contain any of the products."""

    @abstractmethod
    def for_customer(self, customer_id: UUID, page_request: PageRequest) -> Page[WorkOrder]:
        """Newest first."""

    @abstractmethod
    def search_among(
        self, work_order_ids: frozenset[UUID], filters: ExportFilters, page_request: PageRequest
    ) -> Page[WorkOrder]:
        """The O.T.s among ``work_order_ids`` matching the filters, oldest first."""

    @abstractmethod
    def pending_ids(self) -> frozenset[UUID]: ...


class WorkOrderNumberGenerator(ABC):
    """``OT-YYYYMMDD-NNNNN``: local creation date + global consecutive that never restarts."""

    @abstractmethod
    def next_number(self, created_at: datetime) -> str: ...
