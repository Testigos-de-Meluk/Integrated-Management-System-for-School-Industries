"""Public use cases of the virtual assistant (implements ``QuotationRequests``)."""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.products.ports.inbound.product_catalog import ProductCatalog
from modules.quotations.application.item_proposals import AI_UNAVAILABLE, ItemProposer
from modules.quotations.domain.exceptions import InvalidQuotationItems, QuotationNotFound
from modules.quotations.domain.quotation import (
    DEFAULT_VALIDITY_DAYS,
    Quotation,
    QuotationItem,
    RequesterContact,
    validate_quantity,
)
from modules.quotations.ports.inbound.quotation_requests import (
    AssistantOptionsView,
    EstimatedItemView,
    EstimateView,
    ItemProposalView,
    PreliminaryQuotationView,
    ProposedItemView,
    QuotationDocument,
    QuotationRequests,
    RequestedItem,
    RequestQuotationCommand,
)
from modules.quotations.ports.outbound.ports import (
    DispatchDateEstimator,
    PriceEstimator,
    QuotationDocumentGenerator,
    QuotationNumberGenerator,
    QuotationRepository,
)
from modules.shared_kernel.domain.audit import ActorType, AuditAction, AuditRecord
from modules.shared_kernel.domain.exceptions import ServiceUnavailableError, ValidationError
from modules.shared_kernel.domain.money import PriceRange
from modules.shared_kernel.domain.notifications import Attachment, EmailMessage
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger
from modules.shared_kernel.ports.outbound.notifier import Notifier

CONSENT_REQUIRED = "Debe autorizar el tratamiento de sus datos personales para continuar."


def _money(value) -> str | None:
    return str(value) if value is not None else None


def _item_view(item: QuotationItem) -> EstimatedItemView:
    unit, subtotal = item.unit_price_range, item.subtotal_range
    return EstimatedItemView(
        product_id=item.product_id,
        product_code=item.product_code,
        description=item.description,
        unit_of_measure=item.unit_of_measure,
        quantity=item.quantity,
        unit_price_min=_money(unit.min if unit else None),
        unit_price_max=_money(unit.max if unit else None),
        subtotal_min=_money(subtotal.min if subtotal else None),
        subtotal_max=_money(subtotal.max if subtotal else None),
        price_source=item.price_source.value if item.price_source else None,
    )


def _total(items: list[QuotationItem]) -> PriceRange | None:
    ranges = [i.subtotal_range for i in items if i.subtotal_range]
    if not ranges:
        return None
    total = ranges[0]
    for subtotal in ranges[1:]:
        total = total + subtotal
    return total


def preliminary_view(quotation: Quotation) -> PreliminaryQuotationView:
    total = quotation.estimated_total
    return PreliminaryQuotationView(
        id=quotation.id,
        number=quotation.number,
        issued_at=quotation.issued_at,
        valid_until=quotation.valid_until,
        requester_name=quotation.requester.full_name,
        requester_email=quotation.requester.email,
        items=tuple(_item_view(i) for i in quotation.items),
        total_min=_money(total.min if total else None),
        total_max=_money(total.max if total else None),
        unpriced_items=quotation.unpriced_items,
        estimated_dispatch_date=quotation.estimated_dispatch_date,
        access_key=quotation.access_key,
    )


class QuotationRequestService(QuotationRequests):
    def __init__(
        self,
        repository: QuotationRepository,
        numbers: QuotationNumberGenerator,
        catalog: ProductCatalog,
        price_estimator: PriceEstimator,
        dispatch_estimator: DispatchDateEstimator,
        documents: QuotationDocumentGenerator,
        notifier: Notifier,
        audit_logger: AuditLogger,
        validity_days: int = DEFAULT_VALIDITY_DAYS,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        item_proposer: ItemProposer | None = None,
    ) -> None:
        self._proposer = item_proposer
        self._repository = repository
        self._numbers = numbers
        self._catalog = catalog
        self._prices = price_estimator
        self._dispatch = dispatch_estimator
        self._documents = documents
        self._notifier = notifier
        self._audit = audit_logger
        self._validity_days = validity_days
        self._now = clock

    # --- Free text (AI, US 2.41) -------------------------------------------------------------

    def assistant_options(self) -> AssistantOptionsView:
        enabled = self._proposer is not None and self._proposer.available
        return AssistantOptionsView(free_text_enabled=enabled)

    def propose_items(self, description: str) -> ItemProposalView:
        if self._proposer is None:
            raise ServiceUnavailableError(AI_UNAVAILABLE, code="AI_UNAVAILABLE")
        proposal = self._proposer.propose(description)
        return ItemProposalView(
            items=tuple(
                ProposedItemView(
                    product_id=line.product.id,
                    product_code=line.product.code,
                    description=line.product.name,
                    unit_of_measure=line.product.unit_of_measure,
                    quantity=line.quantity,
                )
                for line in proposal.lines
            ),
            unavailable=proposal.unavailable,
        )

    # --- Estimation (no persistence) ----------------------------------------------------------

    def estimate(self, items: tuple[RequestedItem, ...]) -> EstimateView:
        lines = self._build_items(items)
        total = _total(lines)
        return EstimateView(
            items=tuple(_item_view(i) for i in lines),
            total_min=_money(total.min if total else None),
            total_max=_money(total.max if total else None),
            unpriced_items=sum(1 for i in lines if i.unit_price_range is None),
        )

    # --- Request ------------------------------------------------------------------------------

    def request_quotation(
        self, command: RequestQuotationCommand, source_ip: str | None
    ) -> PreliminaryQuotationView:
        if not command.data_consent:
            raise ValidationError.for_field("data_consent", CONSENT_REQUIRED)
        requester = RequesterContact.create(
            command.full_name, command.email, command.phone, command.institution, command.tax_id
        )
        lines = self._build_items(command.items)
        now = self._now()
        quotation = Quotation.request(
            number=self._numbers.next_number(now.year),
            requester=requester,
            items=lines,
            now=now,
            access_key=secrets.token_urlsafe(24),
            suggested_dispatch_date=self._dispatch.suggest(
                [(i.product_id, i.quantity) for i in lines], now.date()
            ),
            validity_days=self._validity_days,
        )
        self._repository.add(quotation)
        self._audit.log(
            AuditRecord(
                action=AuditAction.CREATED,
                entity_type="Quotation",
                entity_id=str(quotation.id),
                actor=None,
                actor_type=ActorType.ANONYMOUS,
                actor_label=f"virtual-assistant:{requester.email}",
                source_ip=source_ip,
                new_values=quotation.snapshot(),
            )
        )
        return preliminary_view(quotation)

    # --- Document -----------------------------------------------------------------------------

    def document(self, quotation_id: UUID, access_key: str) -> QuotationDocument:
        quotation = self._get_with_key(quotation_id, access_key)
        return QuotationDocument(
            filename=f"{quotation.number}.pdf",
            content=self._documents.preliminary_pdf(quotation),
        )

    def email_document(self, quotation_id: UUID, access_key: str) -> str:
        quotation = self._get_with_key(quotation_id, access_key)
        pdf = self._documents.preliminary_pdf(quotation)
        self._notifier.send(
            EmailMessage(
                to=(quotation.requester.email,),
                subject=f"Industrias Escolares · Cotización preliminar {quotation.number}",
                body=_email_body(quotation),
                attachments=(Attachment(f"{quotation.number}.pdf", pdf),),
            )
        )
        return quotation.requester.email

    # --- Helpers ------------------------------------------------------------------------------

    def _build_items(self, requested: tuple[RequestedItem, ...]) -> list[QuotationItem]:
        """Merges repeated products, checks they are active (US 2.7.4) and estimates prices."""
        if not requested:
            raise InvalidQuotationItems("Agregue al menos un producto a la solicitud.")
        quantities: dict[UUID, int] = {}
        for item in requested:
            validate_quantity(item.quantity)
            quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity

        available = self._catalog.selectable_by_ids(list(quantities))
        missing = [pid for pid in quantities if pid not in available]
        if missing:
            raise InvalidQuotationItems(
                "Uno o más productos ya no están disponibles. Retírelos de la solicitud."
            )

        for quantity in quantities.values():
            validate_quantity(quantity)
        estimates = self._prices.estimate(list(quantities.items()))  # one batch (one AI call)
        lines = []
        for product_id, quantity in quantities.items():
            product = available[product_id]
            estimate = estimates.get(product_id)
            lines.append(
                QuotationItem(
                    product_id=product.id,
                    product_code=product.code,
                    description=product.name,
                    unit_of_measure=product.unit_of_measure,
                    quantity=quantity,
                    unit_price_range=estimate.range if estimate else None,
                    price_source=estimate.source if estimate else None,
                )
            )
        return lines

    def _get_with_key(self, quotation_id: UUID, access_key: str) -> Quotation:
        quotation = self._repository.get(quotation_id)
        # Bytes, not str: compare_digest rejects non-ASCII str and would turn a bad key into 500.
        # "replace" keeps a lone surrogate (never valid UTF-8) from raising UnicodeEncodeError.
        expected = quotation.access_key.encode("utf-8") if quotation else b""
        received = (access_key or "").encode("utf-8", "replace")
        if quotation is None or not secrets.compare_digest(expected, received):
            raise QuotationNotFound()  # same answer: do not reveal which quotations exist
        return quotation


def _email_body(quotation: Quotation) -> str:
    return f"""Hola, {quotation.requester.full_name}:

Adjuntamos su cotización preliminar {quotation.number}, válida hasta el
{quotation.valid_until:%d/%m/%Y}.

Los valores son un rango estimado. La administradora revisará su solicitud y le enviará la
cotización formal con los precios, las condiciones y la fecha de despacho definitivos.

Gracias por escribirnos.
Industrias Escolares
"""
