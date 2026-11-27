"""Outbound ports of the Work Orders module."""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.work_orders.domain.work_order import WorkOrder
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


class WorkOrderNumberGenerator(ABC):
    """``OT-YYYYMMDD-NNNNN``: local creation date + global consecutive that never restarts."""

    @abstractmethod
    def next_number(self, created_at: datetime) -> str: ...
