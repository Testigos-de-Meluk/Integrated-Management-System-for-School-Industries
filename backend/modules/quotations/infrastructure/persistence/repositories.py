"""PostgreSQL adapters of the Quotations module."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Coalesce

from modules.quotations.domain.pricing import PriceSource
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
from modules.quotations.ports.inbound.quotation_review import QuotationFilters
from modules.quotations.ports.outbound.ports import (
    DispatchDateEstimator,
    PriceHistory,
    PriceSample,
    QuotationNumberGenerator,
    QuotationRepository,
)
from modules.shared_kernel.domain.money import PriceRange
from modules.shared_kernel.domain.pagination import Page, PageRequest


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
            price_source=PriceSource(item.price_source) if item.price_source else None,
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
        approved_at=model.approved_at,
        approved_by_id=model.approved_by_id,
        approved_by_name=model.approved_by_name,
    )


def _header_fields(quotation: Quotation) -> dict:
    total = quotation.estimated_total
    return {
        "quotation_number": quotation.number,
        "customer_id": quotation.customer_id,
        "issued_at": quotation.issued_at,
        "requester_full_name": quotation.requester.full_name,
        "requester_email": quotation.requester.email,
        "requester_phone": quotation.requester.phone,
        "requester_institution": quotation.requester.institution,
        "requester_tax_id": quotation.requester.tax_id,
        "commercial_terms": quotation.commercial_terms,
        "valid_until": quotation.valid_until,
        "estimated_dispatch_date": quotation.estimated_dispatch_date,
        "dispatch_date_source": (
            quotation.dispatch_date_source.value if quotation.dispatch_date_source else ""
        ),
        "status": quotation.status.value,
        "rejection_reason": quotation.rejection_reason,
        "access_key": quotation.access_key,
        "estimated_total_min": total.min if total else None,
        "estimated_total_max": total.max if total else None,
        "final_total": quotation.final_total,
        "approved_at": quotation.approved_at,
        "approved_by_id": quotation.approved_by_id,
        "approved_by_name": quotation.approved_by_name,
    }


def _item_models(quotation: Quotation, model: QuotationModel) -> list[QuotationItemModel]:
    return [
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
            price_source=item.price_source.value if item.price_source else "",
        )
        for position, item in enumerate(quotation.items)
    ]


def _page(queryset, page_request: PageRequest) -> Page[Quotation]:
    total = queryset.count()
    start = page_request.offset
    models = queryset.prefetch_related("items").order_by("-issued_at", "-quotation_number")[
        start : start + page_request.size
    ]
    return Page([_to_domain(m) for m in models], total, page_request)


class DjangoQuotationRepository(QuotationRepository):
    def add(self, quotation: Quotation) -> None:
        model = QuotationModel.objects.create(id=quotation.id, **_header_fields(quotation))
        QuotationItemModel.objects.bulk_create(_item_models(quotation, model))

    def get(self, quotation_id: UUID) -> Quotation | None:
        model = QuotationModel.objects.prefetch_related("items").filter(pk=quotation_id).first()
        return _to_domain(model) if model else None

    def update(self, quotation: Quotation) -> None:
        model = QuotationModel.objects.select_for_update().get(pk=quotation.id)
        for name, value in _header_fields(quotation).items():
            setattr(model, name, value)
        model.save()
        model.items.all().delete()
        QuotationItemModel.objects.bulk_create(_item_models(quotation, model))

    def search(self, filters: QuotationFilters, page_request: PageRequest) -> Page[Quotation]:
        queryset = QuotationModel.objects.all()
        if filters.issued_from:
            queryset = queryset.filter(issued_at__date__gte=filters.issued_from)
        if filters.issued_to:
            queryset = queryset.filter(issued_at__date__lte=filters.issued_to)
        if filters.contact and (text := filters.contact.strip()):
            queryset = queryset.filter(
                Q(requester_full_name__icontains=text)
                | Q(requester_email__icontains=text)
                | Q(requester_phone__icontains=text)
                | Q(requester_institution__icontains=text)
                | Q(requester_tax_id__icontains=text)
            )
        if filters.product and (text := filters.product.strip()):
            matching = QuotationItemModel.objects.filter(
                Q(product_code__icontains=text) | Q(description__icontains=text)
            ).values("quotation_id")
            queryset = queryset.filter(pk__in=matching)
        if filters.total_min is not None or filters.total_max is not None:
            # The amount is the final total once approved, the estimated range before.
            queryset = queryset.annotate(
                amount_low=Coalesce("final_total", "estimated_total_min"),
                amount_high=Coalesce("final_total", "estimated_total_max"),
            )
            if filters.total_min is not None:
                queryset = queryset.filter(amount_high__gte=filters.total_min)
            if filters.total_max is not None:
                queryset = queryset.filter(amount_low__lte=filters.total_max)
        if filters.status:
            queryset = queryset.filter(status=filters.status)
        return _page(queryset, page_request)

    def for_customer(self, customer_id: UUID, page_request: PageRequest) -> Page[Quotation]:
        return _page(QuotationModel.objects.filter(customer_id=customer_id), page_request)


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

    def reference_samples(self, since: datetime, limit: int) -> list[PriceSample]:
        rows = (
            QuotationItemModel.objects.filter(
                final_unit_price__isnull=False,
                quotation__status=QuotationModel.Status.APPROVED,
                quotation__issued_at__gte=since,
            )
            .order_by("-quotation__issued_at")
            .values(
                "product_id",
                "product_code",
                "description",
                "unit_of_measure",
                "quantity",
                "final_unit_price",
            )[: limit * 10]
        )
        samples: dict[UUID, PriceSample] = {}
        for row in rows:  # newest first: keep the latest price of each product
            if row["product_id"] not in samples:
                samples[row["product_id"]] = PriceSample(
                    product_id=row["product_id"],
                    product_code=row["product_code"],
                    description=row["description"],
                    unit_of_measure=row["unit_of_measure"],
                    quantity=row["quantity"],
                    unit_price=row["final_unit_price"],
                )
            if len(samples) == limit:
                break
        return list(samples.values())


class NoHistoryDispatchDateEstimator(DispatchDateEstimator):
    """TEMPORARY strategy: the median of real dispatch times needs work orders with their actual
    dispatch date (roadmap step 5). Until then there is never enough history (FR-02-06), so the
    Administrador enters the date manually."""

    def suggest(self, items: list[tuple[UUID, int]], today: date) -> date | None:
        return None
