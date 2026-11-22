"""PostgreSQL adapters of the Quotations module."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from modules.quotations.domain.quotation import (
    DispatchDateSource,
    Quotation,
    QuotationItem,
    QuotationStatus,
    RequesterContact,
)
from modules.quotations.infrastructure.models import (
    QuotationItemModel,
    QuotationModel,
    QuotationSequenceModel,
)
from modules.quotations.ports.outbound.ports import (
    DispatchDateEstimator,
    PriceHistory,
    QuotationNumberGenerator,
    QuotationRepository,
)
from modules.shared_kernel.domain.money import PriceRange


def _to_domain(model: QuotationModel) -> Quotation:
    items = [
        QuotationItem(
            id=item.id,
            product_id=item.product_id,
            product_code=item.product_code,
            description=item.description,
            unit_of_measure=item.unit_of_measure,
            quantity=item.quantity,
            unit_price_range=(
                PriceRange(item.unit_price_min, item.unit_price_max)
                if item.unit_price_min is not None
                else None
            ),
            final_unit_price=item.final_unit_price,
        )
        for item in model.items.all()
    ]
    return Quotation(
        id=model.id,
        number=model.quotation_number,
        issued_at=model.issued_at,
        requester=RequesterContact(
            model.requester_full_name,
            model.requester_email,
            model.requester_phone,
            model.requester_institution,
            model.requester_tax_id,
        ),
        items=items,
        valid_until=model.valid_until,
        status=QuotationStatus(model.status),
        customer_id=model.customer_id,
        estimated_dispatch_date=model.estimated_dispatch_date,
        dispatch_date_source=(
            DispatchDateSource(model.dispatch_date_source) if model.dispatch_date_source else None
        ),
        commercial_terms=model.commercial_terms,
        rejection_reason=model.rejection_reason,
        access_key=model.access_key,
    )


class DjangoQuotationRepository(QuotationRepository):
    def add(self, quotation: Quotation) -> None:
        model = QuotationModel.objects.create(
            id=quotation.id,
            quotation_number=quotation.number,
            customer_id=quotation.customer_id,
            issued_at=quotation.issued_at,
            requester_full_name=quotation.requester.full_name,
            requester_email=quotation.requester.email,
            requester_phone=quotation.requester.phone,
            requester_institution=quotation.requester.institution,
            requester_tax_id=quotation.requester.tax_id,
            commercial_terms=quotation.commercial_terms,
            valid_until=quotation.valid_until,
            estimated_dispatch_date=quotation.estimated_dispatch_date,
            dispatch_date_source=(
                quotation.dispatch_date_source.value if quotation.dispatch_date_source else ""
            ),
            status=quotation.status.value,
            rejection_reason=quotation.rejection_reason,
            access_key=quotation.access_key,
        )
        QuotationItemModel.objects.bulk_create(
            [
                QuotationItemModel(
                    id=item.id,
                    quotation=model,
                    position=position,
                    product_id=item.product_id,
                    product_code=item.product_code,
                    description=item.description,
                    unit_of_measure=item.unit_of_measure,
                    quantity=item.quantity,
                    unit_price_min=item.unit_price_range.min if item.unit_price_range else None,
                    unit_price_max=item.unit_price_range.max if item.unit_price_range else None,
                    final_unit_price=item.final_unit_price,
                )
                for position, item in enumerate(quotation.items)
            ]
        )

    def get(self, quotation_id: UUID) -> Quotation | None:
        model = QuotationModel.objects.prefetch_related("items").filter(pk=quotation_id).first()
        return _to_domain(model) if model else None


class DjangoQuotationNumberGenerator(QuotationNumberGenerator):
    def next_number(self, year: int) -> str:
        with transaction.atomic():
            sequence, _ = QuotationSequenceModel.objects.select_for_update().get_or_create(
                year=year
            )
            sequence.last_number += 1
            sequence.save(update_fields=["last_number"])
        return f"COT-{year}-{sequence.last_number:04d}"


class DjangoPriceHistory(PriceHistory):
    def approved_unit_prices(self, product_id: UUID, since: datetime) -> list[Decimal]:
        return list(
            QuotationItemModel.objects.filter(
                product_id=product_id,
                final_unit_price__isnull=False,
                quotation__status=QuotationModel.Status.APPROVED,
                quotation__issued_at__gte=since,
            )
            .order_by("-quotation__issued_at")
            .values_list("final_unit_price", flat=True)[:200]
        )


class NoHistoryDispatchDateEstimator(DispatchDateEstimator):
    """TEMPORARY strategy: the median of real dispatch times needs work orders with their actual
    dispatch date (roadmap step 5). Until then there is never enough history (FR-02-06), so the
    Administrador enters the date manually."""

    def suggest(self, items: list[tuple[UUID, int]], today: date) -> date | None:
        return None
