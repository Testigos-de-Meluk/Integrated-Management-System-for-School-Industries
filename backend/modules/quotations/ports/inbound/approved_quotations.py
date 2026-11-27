"""Inbound port used by OTHER MODULES: approved quotations, the source of work orders (FR-02-20).

The work orders module reads them to generate an O.T. and links a customer when the quotation has
none (the only change allowed after approval, FR-02-15). It does not grant ``QUOTATION_MANAGE``:
the read access is part of ``WORK_ORDER_MANAGE`` (corrections README, 4.4), which is checked here.
No prices cross this port: work orders have none.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor


@dataclass(frozen=True, slots=True)
class ApprovedItemView:
    product_id: UUID
    product_code: str
    description: str
    unit_of_measure: str
    quantity: int


@dataclass(frozen=True, slots=True)
class ApprovedQuotationView:
    id: UUID
    number: str
    approved_at: datetime
    requester_name: str
    requester_institution: str
    requester_tax_id: str
    customer_id: UUID | None
    dispatch_date: date | None
    items: tuple[ApprovedItemView, ...]


class ApprovedQuotations(ABC):
    @abstractmethod
    def search_approved(
        self,
        actor: Actor,
        text: str | None,
        excluded_ids: frozenset[UUID],
        page_request: PageRequest,
    ) -> Page[ApprovedQuotationView]:
        """Approved quotations, newest approval first, leaving out ``excluded_ids`` (those that
        already have an active O.T.). ``text`` matches the number or the requester."""

    @abstractmethod
    def get_approved(self, actor: Actor, quotation_id: UUID) -> ApprovedQuotationView:
        """Raises ``NotFoundError`` if it does not exist or is not approved."""

    @abstractmethod
    def link_customer(self, actor: Actor, quotation_id: UUID, customer_id: UUID) -> None:
        """Links an active customer to an approved quotation that has none (audited here)."""
