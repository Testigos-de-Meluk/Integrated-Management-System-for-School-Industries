"""Approved quotations for the work orders module (implements ``ApprovedQuotations``, FR-02-20).

Requires ``WORK_ORDER_MANAGE``: the Operador generates O.T.s without being able to review
quotations (corrections README, 4.4).
"""

from uuid import UUID

from modules.customers.ports.inbound.customer_directory import CustomerDirectory
from modules.quotations.application.quotation_review_service import ACTIVE_CUSTOMER_REQUIRED
from modules.quotations.domain.exceptions import QuotationNotFound
from modules.quotations.domain.quotation import Quotation, QuotationStatus
from modules.quotations.ports.inbound.approved_quotations import (
    ApprovedItemView,
    ApprovedQuotations,
    ApprovedQuotationView,
)
from modules.quotations.ports.outbound.ports import QuotationRepository
from modules.shared_kernel.domain.audit import AuditAction, AuditRecord
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger


def approved_view(quotation: Quotation) -> ApprovedQuotationView:
    requester = quotation.requester
    return ApprovedQuotationView(
        id=quotation.id,
        number=quotation.number,
        approved_at=quotation.approved_at or quotation.issued_at,
        requester_name=requester.full_name,
        requester_institution=requester.institution,
        requester_tax_id=requester.tax_id,
        customer_id=quotation.customer_id,
        dispatch_date=quotation.estimated_dispatch_date,
        items=tuple(
            ApprovedItemView(
                i.product_id, i.product_code, i.description, i.unit_of_measure, i.quantity
            )
            for i in quotation.items
        ),
    )


class ApprovedQuotationsService(ApprovedQuotations):
    def __init__(
        self,
        repository: QuotationRepository,
        customers: CustomerDirectory,
        audit_logger: AuditLogger,
    ) -> None:
        self._repository = repository
        self._customers = customers
        self._audit = audit_logger

    def search_approved(
        self,
        actor: Actor,
        text: str | None,
        excluded_ids: frozenset[UUID],
        page_request: PageRequest,
    ) -> Page[ApprovedQuotationView]:
        actor.require(Permission.WORK_ORDER_MANAGE)
        page = self._repository.search_approved(
            (text or "").strip() or None, excluded_ids, page_request
        )
        return Page([approved_view(q) for q in page.items], page.total, page.request)

    def get_approved(self, actor: Actor, quotation_id: UUID) -> ApprovedQuotationView:
        actor.require(Permission.WORK_ORDER_MANAGE)
        return approved_view(self._approved_or_fail(quotation_id))

    def link_customer(self, actor: Actor, quotation_id: UUID, customer_id: UUID) -> None:
        actor.require(Permission.WORK_ORDER_MANAGE)
        quotation = self._approved_or_fail(quotation_id)
        customer = self._customers.by_id(customer_id)
        if customer is None or not customer.is_active:
            raise ValidationError.for_field("customer_id", ACTIVE_CUSTOMER_REQUIRED)
        before = quotation.snapshot()
        quotation.link_customer(customer_id)  # only allowed while it has none (FR-02-15)
        self._repository.update(quotation)
        self._audit.log(
            AuditRecord(
                action=AuditAction.UPDATED,
                entity_type="Quotation",
                entity_id=str(quotation.id),
                actor=actor,
                old_values=before,
                new_values=quotation.snapshot(),
                reason="Cliente vinculado al generar la orden de trabajo",
            )
        )

    def _approved_or_fail(self, quotation_id: UUID) -> Quotation:
        quotation = self._repository.get(quotation_id)
        if quotation is None or quotation.status is not QuotationStatus.APPROVED:
            raise QuotationNotFound()
        return quotation
