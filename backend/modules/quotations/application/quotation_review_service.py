"""Review of quotations by the Administrador (implements ``QuotationReview``).

Every use case requires ``QUOTATION_MANAGE`` (Administrador, Superadministrador; the Operador is
denied, US 2.25.4).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from modules.customers.ports.inbound.customer_directory import CustomerDirectory, CustomerSummary
from modules.products.ports.inbound.product_catalog import ProductCatalog
from modules.quotations.domain.events import QuotationApproved
from modules.quotations.domain.exceptions import InvalidQuotationItems, QuotationNotFound
from modules.quotations.domain.quotation import (
    DEFAULT_VALIDITY_DAYS,
    REASON_MAX_LENGTH,
    Quotation,
    QuotationItem,
    QuotationStatus,
    clean_multiline_text,
    validate_quantity,
)
from modules.quotations.ports.inbound.customer_quotations import (
    CustomerQuotations,
    CustomerQuotationView,
)
from modules.quotations.ports.inbound.quotation_review import (
    ApproveQuotationCommand,
    LinkedCustomerView,
    ModifyQuotationCommand,
    QuotationDetailView,
    QuotationFile,
    QuotationFilters,
    QuotationReview,
    QuotationSummaryView,
    ReviewedItem,
    ReviewItemView,
)
from modules.quotations.ports.outbound.ports import (
    DispatchDateEstimator,
    PriceEstimator,
    QuotationDocumentGenerator,
    QuotationRepository,
)
from modules.shared_kernel.domain.audit import AuditAction, AuditRecord
from modules.shared_kernel.domain.document_numbers import business_date
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.notifications import Attachment, EmailMessage
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger
from modules.shared_kernel.ports.outbound.event_publisher import EventPublisher
from modules.shared_kernel.ports.outbound.notifier import Notifier

ONLY_ACTIVE_PRODUCTS = "Solo puede agregar productos activos del catálogo."
ACTIVE_CUSTOMER_REQUIRED = "Seleccione un cliente registrado y activo."


def _money(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _item_view(item: QuotationItem) -> ReviewItemView:
    unit, subtotal = item.unit_price_range, item.subtotal_range
    return ReviewItemView(
        id=item.id,
        product_id=item.product_id,
        product_code=item.product_code,
        description=item.description,
        unit_of_measure=item.unit_of_measure,
        quantity=item.quantity,
        unit_price_min=_money(unit.min if unit else None),
        unit_price_max=_money(unit.max if unit else None),
        subtotal_min=_money(subtotal.min if subtotal else None),
        subtotal_max=_money(subtotal.max if subtotal else None),
        final_unit_price=_money(item.final_unit_price),
        final_subtotal=_money(item.final_subtotal),
        price_source=item.price_source.value if item.price_source else None,
    )


def _customer_view(customer: CustomerSummary | None) -> LinkedCustomerView | None:
    if customer is None:
        return None
    return LinkedCustomerView(customer.id, customer.tax_id, customer.name, customer.is_active)


def summary_view(quotation: Quotation) -> QuotationSummaryView:
    total = quotation.estimated_total
    requester = quotation.requester
    return QuotationSummaryView(
        id=quotation.id,
        number=quotation.number,
        issued_at=quotation.issued_at,
        status=quotation.status.value,
        requester_name=requester.full_name,
        requester_email=requester.email,
        requester_phone=requester.phone,
        requester_institution=requester.institution,
        products=tuple(i.description for i in quotation.items),
        total_min=_money(total.min if total else None),
        total_max=_money(total.max if total else None),
        final_total=_money(quotation.final_total),
        unpriced_items=quotation.unpriced_items,
        has_customer=quotation.customer_id is not None,
    )


class QuotationReviewService(QuotationReview):
    def __init__(
        self,
        repository: QuotationRepository,
        catalog: ProductCatalog,
        customers: CustomerDirectory,
        price_estimator: PriceEstimator,
        dispatch_estimator: DispatchDateEstimator,
        documents: QuotationDocumentGenerator,
        notifier: Notifier,
        events: EventPublisher,
        audit_logger: AuditLogger,
        validity_days: int = DEFAULT_VALIDITY_DAYS,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._customers = customers
        self._prices = price_estimator
        self._dispatch = dispatch_estimator
        self._documents = documents
        self._notifier = notifier
        self._events = events
        self._audit = audit_logger
        self._validity_days = validity_days
        self._now = clock

    # --- Queries ------------------------------------------------------------------------------

    def list_quotations(
        self, actor: Actor, filters: QuotationFilters, page_request: PageRequest
    ) -> Page[QuotationSummaryView]:
        actor.require(Permission.QUOTATION_MANAGE)
        if filters.issued_from and filters.issued_to and filters.issued_from > filters.issued_to:
            raise ValidationError.for_field(
                "issued_to", "La fecha final debe ser igual o posterior a la inicial."
            )
        if (
            filters.total_min is not None
            and filters.total_max is not None
            and filters.total_min > filters.total_max
        ):
            raise ValidationError.for_field(
                "total_max", "El monto máximo debe ser mayor o igual al mínimo."
            )
        page = self._repository.search(filters, page_request)
        return Page([summary_view(q) for q in page.items], page.total, page.request)

    def get_quotation(self, actor: Actor, quotation_id: UUID) -> QuotationDetailView:
        actor.require(Permission.QUOTATION_MANAGE)
        return self._detail(self._get_or_fail(quotation_id))

    def document(self, actor: Actor, quotation_id: UUID) -> QuotationFile:
        actor.require(Permission.QUOTATION_MANAGE)
        quotation = self._get_or_fail(quotation_id)
        return QuotationFile(f"{quotation.number}.pdf", self._pdf(quotation))

    # --- Commands -----------------------------------------------------------------------------

    def modify_quotation(
        self, actor: Actor, quotation_id: UUID, command: ModifyQuotationCommand
    ) -> QuotationDetailView:
        actor.require(Permission.QUOTATION_MANAGE)
        quotation = self._get_or_fail(quotation_id)
        quotation.ensure_editable()
        reason = self._required_reason(command.reason, "Indique el motivo de la modificación.")
        before = quotation.snapshot()
        items = self._reviewed_items(quotation, command.items)
        today = business_date(self._now())
        quotation.modify(
            items,
            command.commercial_terms,
            command.dispatch_date,
            today,
            suggested_dispatch_date=self._dispatch.suggest(
                [(i.product_id, i.quantity) for i in items], today
            ),
        )
        self._repository.update(quotation)
        self._log(AuditAction.UPDATED, actor, quotation, before, reason)
        return self._detail(quotation)

    def approve_quotation(
        self, actor: Actor, quotation_id: UUID, command: ApproveQuotationCommand
    ) -> QuotationDetailView:
        actor.require(Permission.QUOTATION_MANAGE)
        quotation = self._get_or_fail(quotation_id)
        before = quotation.snapshot()
        now = self._now()
        quotation.approve(
            {p.item_id: p.final_unit_price for p in command.prices},
            command.dispatch_date,
            command.commercial_terms,
            actor.user_id,
            actor.display_name or actor.role.value,
            now,
            self._validity_days,
            suggested_dispatch_date=self._suggested_dispatch(quotation),
        )
        self._repository.update(quotation)
        self._log(AuditAction.APPROVED, actor, quotation, before)
        self._events.publish(
            QuotationApproved(
                quotation_id=quotation.id,
                number=quotation.number,
                customer_id=quotation.customer_id,
                approved_at=now,
                occurred_at=now,
            )
        )
        pdf = self._documents.formal_pdf(quotation)
        self._notifier.send(  # US 2.27.3
            EmailMessage(
                to=(quotation.requester.email,),
                subject=f"Industrias Escolares · Cotización {quotation.number} aprobada",
                body=_approved_body(quotation),
                attachments=(Attachment(f"{quotation.number}.pdf", pdf),),
            )
        )
        return self._detail(quotation)

    def reject_quotation(
        self, actor: Actor, quotation_id: UUID, reason: str
    ) -> QuotationDetailView:
        actor.require(Permission.QUOTATION_MANAGE)
        quotation = self._get_or_fail(quotation_id)
        before = quotation.snapshot()
        quotation.reject(reason)
        self._repository.update(quotation)
        self._log(AuditAction.REJECTED, actor, quotation, before, quotation.rejection_reason)
        self._notifier.send(  # US 2.29.5
            EmailMessage(
                to=(quotation.requester.email,),
                subject=f"Industrias Escolares · Su solicitud de cotización {quotation.number}",
                body=_rejected_body(quotation),
            )
        )
        return self._detail(quotation)

    def link_customer(
        self, actor: Actor, quotation_id: UUID, customer_id: UUID | None
    ) -> QuotationDetailView:
        actor.require(Permission.QUOTATION_MANAGE)
        quotation = self._get_or_fail(quotation_id)
        if customer_id is not None:
            customer = self._customers.by_id(customer_id)
            if customer is None or not customer.is_active:
                raise ValidationError.for_field("customer_id", ACTIVE_CUSTOMER_REQUIRED)
        before = quotation.snapshot()
        quotation.link_customer(customer_id)
        self._repository.update(quotation)
        self._log(AuditAction.UPDATED, actor, quotation, before)
        return self._detail(quotation)

    # --- Helpers ------------------------------------------------------------------------------

    def _reviewed_items(
        self, quotation: Quotation, reviewed: tuple[ReviewedItem, ...]
    ) -> list[QuotationItem]:
        """Keeps the snapshots and estimates of the products already quoted; new products must be
        active in the catalog (US 2.28.4) and get their own estimate."""
        if not reviewed:
            raise InvalidQuotationItems("La cotización debe tener al menos un producto.")
        merged: dict[UUID, ReviewedItem] = {}
        for item in reviewed:
            validate_quantity(item.quantity)
            previous = merged.get(item.product_id)
            if previous is None:
                merged[item.product_id] = item
            else:
                merged[item.product_id] = ReviewedItem(
                    item.product_id,
                    previous.quantity + item.quantity,
                    item.final_unit_price
                    if item.final_unit_price is not None
                    else previous.final_unit_price,
                )

        current = {i.product_id: i for i in quotation.items}
        new_ids = [pid for pid in merged if pid not in current]
        available = self._catalog.selectable_by_ids(new_ids) if new_ids else {}
        if any(pid not in available for pid in new_ids):
            raise InvalidQuotationItems(ONLY_ACTIVE_PRODUCTS)
        estimates = (
            self._prices.estimate([(pid, merged[pid].quantity) for pid in new_ids])
            if new_ids
            else {}
        )

        lines: list[QuotationItem] = []
        for product_id, item in merged.items():
            if product_id in current:
                existing = current[product_id]
                lines.append(
                    QuotationItem(
                        id=existing.id,
                        product_id=existing.product_id,
                        product_code=existing.product_code,
                        description=existing.description,
                        unit_of_measure=existing.unit_of_measure,
                        quantity=item.quantity,
                        unit_price_range=existing.unit_price_range,
                        final_unit_price=item.final_unit_price,
                        price_source=existing.price_source,
                    )
                )
            else:
                product = available[product_id]
                estimate = estimates.get(product_id)
                lines.append(
                    QuotationItem(
                        product_id=product.id,
                        product_code=product.code,
                        description=product.name,
                        unit_of_measure=product.unit_of_measure,
                        quantity=item.quantity,
                        unit_price_range=estimate.range if estimate else None,
                        final_unit_price=item.final_unit_price,
                        price_source=estimate.source if estimate else None,
                    )
                )
        return lines

    def _suggested_dispatch(self, quotation: Quotation):
        """The median recalculated now (FR-02-06): there may be more history than when the
        quotation was requested. Only while it can still change."""
        if not quotation.is_editable:
            return None
        return self._dispatch.suggest(
            [(i.product_id, i.quantity) for i in quotation.items], business_date(self._now())
        )

    def _detail(self, quotation: Quotation) -> QuotationDetailView:
        total = quotation.estimated_total
        requester = quotation.requester
        customer = self._customers.by_id(quotation.customer_id) if quotation.customer_id else None
        suggested = None
        if customer is None and requester.tax_id and quotation.status != QuotationStatus.REJECTED:
            match = self._customers.by_tax_id(requester.tax_id)
            suggested = match if match and match.is_active else None
        return QuotationDetailView(
            id=quotation.id,
            number=quotation.number,
            issued_at=quotation.issued_at,
            valid_until=quotation.valid_until,
            status=quotation.status.value,
            is_editable=quotation.is_editable,
            requester_name=requester.full_name,
            requester_email=requester.email,
            requester_phone=requester.phone,
            requester_institution=requester.institution,
            requester_tax_id=requester.tax_id,
            items=tuple(_item_view(i) for i in quotation.items),
            total_min=_money(total.min if total else None),
            total_max=_money(total.max if total else None),
            final_total=_money(quotation.final_total),
            unpriced_items=quotation.unpriced_items,
            estimated_dispatch_date=quotation.estimated_dispatch_date,
            dispatch_date_source=(
                quotation.dispatch_date_source.value if quotation.dispatch_date_source else None
            ),
            commercial_terms=quotation.commercial_terms,
            rejection_reason=quotation.rejection_reason,
            approved_at=quotation.approved_at,
            approved_by_name=quotation.approved_by_name,
            customer=_customer_view(customer),
            suggested_customer=_customer_view(suggested),
            suggested_dispatch_date=self._suggested_dispatch(quotation),
        )

    def _pdf(self, quotation: Quotation) -> bytes:
        if quotation.status is QuotationStatus.APPROVED:
            return self._documents.formal_pdf(quotation)
        return self._documents.preliminary_pdf(quotation)

    @staticmethod
    def _required_reason(reason: str | None, message: str) -> str:
        text = clean_multiline_text(reason, "reason", REASON_MAX_LENGTH)
        if not text:
            raise ValidationError.for_field("reason", message)
        return text

    def _get_or_fail(self, quotation_id: UUID) -> Quotation:
        quotation = self._repository.get(quotation_id)
        if quotation is None:
            raise QuotationNotFound()
        return quotation

    def _log(
        self,
        action: AuditAction,
        actor: Actor,
        quotation: Quotation,
        before: dict,
        reason: str | None = None,
    ) -> None:
        self._audit.log(
            AuditRecord(
                action=action,
                entity_type="Quotation",
                entity_id=str(quotation.id),
                actor=actor,
                old_values=before,
                new_values=quotation.snapshot(),
                reason=reason,
            )
        )


class CustomerQuotationsService(CustomerQuotations):
    """Quotations of a customer for its 360 profile (customers module, US 2.20)."""

    def __init__(self, repository: QuotationRepository) -> None:
        self._repository = repository

    def quotations_of(
        self, customer_id: UUID, page_request: PageRequest
    ) -> Page[CustomerQuotationView]:
        page = self._repository.for_customer(customer_id, page_request)
        items = [
            CustomerQuotationView(q.id, q.number, q.issued_at, q.status.value) for q in page.items
        ]
        return Page(items, page.total, page.request)


def _approved_body(quotation: Quotation) -> str:
    dispatch = quotation.estimated_dispatch_date
    terms = (
        f"\nCondiciones comerciales:\n{quotation.commercial_terms}\n"
        if quotation.commercial_terms
        else ""
    )
    return f"""Hola, {quotation.requester.full_name}:

Su cotización {quotation.number} fue aprobada. Adjuntamos la cotización formal con los precios
definitivos, válida hasta el {quotation.valid_until:%d/%m/%Y}.

Fecha de despacho: {dispatch:%d/%m/%Y}
{terms}
Si tiene preguntas, responda a este correo.

Industrias Escolares
"""


def _rejected_body(quotation: Quotation) -> str:
    return f"""Hola, {quotation.requester.full_name}:

Revisamos su solicitud de cotización {quotation.number} y no es posible atenderla en esta
ocasión, por el siguiente motivo:

{quotation.rejection_reason}

Puede enviarnos una nueva solicitud cuando lo desee.

Industrias Escolares
"""
