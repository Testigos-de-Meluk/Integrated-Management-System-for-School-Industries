"""PostgreSQL adapters of the Work Orders module."""

from datetime import date, datetime
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from modules.shared_kernel.domain.document_numbers import document_number
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.work_orders.domain.exceptions import ActiveWorkOrderExists
from modules.work_orders.domain.work_order import (
    WorkOrder,
    WorkOrderCustomer,
    WorkOrderItem,
    WorkOrderStatus,
)
from modules.work_orders.infrastructure.models import (
    WorkOrderCounterModel,
    WorkOrderItemModel,
    WorkOrderModel,
)
from modules.work_orders.ports.inbound.exportable_work_orders import ExportFilters
from modules.work_orders.ports.inbound.work_order_management import WorkOrderFilters
from modules.work_orders.ports.outbound.ports import WorkOrderNumberGenerator, WorkOrderRepository

WORK_ORDER_PREFIX = "OT"
_ACTIVE = ~Q(status=WorkOrderModel.Status.CANCELLED)


def _to_domain(model: WorkOrderModel) -> WorkOrder:
    return WorkOrder(
        id=model.id,
        number=model.order_number,
        quotation_id=model.quotation_id,
        quotation_number=model.quotation_number,
        quotation_approved_at=model.quotation_approved_at,
        customer=WorkOrderCustomer(model.customer_id, model.customer_tax_id, model.customer_name),
        items=[
            WorkOrderItem(
                id=item.id,
                product_id=item.product_id,
                product_code=item.product_code,
                description=item.description,
                unit_of_measure=item.unit_of_measure,
                quantity=item.quantity,
            )
            for item in model.items.all()
        ],
        agreed_delivery_date=model.agreed_delivery_date,
        actual_dispatch_date=model.actual_dispatch_date,
        status=WorkOrderStatus(model.status),
        cancellation_reason=model.cancellation_reason,
        created_at=model.created_at,
        created_by_id=model.created_by_id,
        created_by_name=model.created_by_name,
    )


def _header_fields(order: WorkOrder) -> dict:
    return {
        "order_number": order.number,
        "quotation_id": order.quotation_id,
        "quotation_number": order.quotation_number,
        "quotation_approved_at": order.quotation_approved_at,
        "customer_id": order.customer.id,
        "customer_tax_id": order.customer.tax_id,
        "customer_name": order.customer.name,
        "agreed_delivery_date": order.agreed_delivery_date,
        "actual_dispatch_date": order.actual_dispatch_date,
        "status": order.status.value,
        "cancellation_reason": order.cancellation_reason,
        "created_at": order.created_at,
        "created_by_id": order.created_by_id,
        "created_by_name": order.created_by_name,
    }


def _item_models(order: WorkOrder, model: WorkOrderModel) -> list[WorkOrderItemModel]:
    return [
        WorkOrderItemModel(
            id=item.id,
            work_order=model,
            position=position,
            product_id=item.product_id,
            product_code=item.product_code,
            description=item.description,
            unit_of_measure=item.unit_of_measure,
            quantity=item.quantity,
        )
        for position, item in enumerate(order.items)
    ]


class DjangoWorkOrderRepository(WorkOrderRepository):
    def add(self, work_order: WorkOrder) -> None:
        try:
            # Savepoint: a second O.T. generated at the same time breaks the partial unique index;
            # the request gets a clear 409 instead of a broken transaction.
            with transaction.atomic():
                model = WorkOrderModel.objects.create(
                    id=work_order.id, **_header_fields(work_order)
                )
        except IntegrityError as error:
            raise ActiveWorkOrderExists() from error
        WorkOrderItemModel.objects.bulk_create(_item_models(work_order, model))

    def get(self, work_order_id: UUID) -> WorkOrder | None:
        model = WorkOrderModel.objects.prefetch_related("items").filter(pk=work_order_id).first()
        return _to_domain(model) if model else None

    def update(self, work_order: WorkOrder) -> None:
        model = WorkOrderModel.objects.select_for_update().get(pk=work_order.id)
        for name, value in _header_fields(work_order).items():
            setattr(model, name, value)
        model.save()
        model.items.all().delete()
        WorkOrderItemModel.objects.bulk_create(_item_models(work_order, model))

    def search(self, filters: WorkOrderFilters, page_request: PageRequest) -> Page[WorkOrder]:
        queryset = WorkOrderModel.objects.all()
        if filters.number and (text := filters.number.strip()):
            queryset = queryset.filter(order_number__icontains=text)
        if filters.quotation_number and (text := filters.quotation_number.strip()):
            queryset = queryset.filter(quotation_number__icontains=text)
        if filters.customer and (text := filters.customer.strip()):
            queryset = queryset.filter(
                Q(customer_name__icontains=text) | Q(customer_tax_id__icontains=text)
            )
        if filters.product and (text := filters.product.strip()):
            matching = WorkOrderItemModel.objects.filter(
                Q(product_code__icontains=text) | Q(description__icontains=text)
            ).values("work_order_id")
            queryset = queryset.filter(pk__in=matching)
        if filters.agreed_from:
            queryset = queryset.filter(agreed_delivery_date__gte=filters.agreed_from)
        if filters.agreed_to:
            queryset = queryset.filter(agreed_delivery_date__lte=filters.agreed_to)
        if filters.status:
            queryset = queryset.filter(status=filters.status)
        total = queryset.count()
        start = page_request.offset
        models = queryset.prefetch_related("items").order_by("-created_at", "-order_number")[
            start : start + page_request.size
        ]
        return Page([_to_domain(m) for m in models], total, page_request)

    def search_among(
        self, work_order_ids: frozenset[UUID], filters: ExportFilters, page_request: PageRequest
    ) -> Page[WorkOrder]:
        queryset = WorkOrderModel.objects.filter(pk__in=work_order_ids)
        if filters.number and (text := filters.number.strip()):
            queryset = queryset.filter(order_number__icontains=text)
        if filters.customer and (text := filters.customer.strip()):
            queryset = queryset.filter(
                Q(customer_name__icontains=text) | Q(customer_tax_id__icontains=text)
            )
        # ``__date`` uses the active time zone (America/Bogota): the local generation date.
        if filters.created_from:
            queryset = queryset.filter(created_at__date__gte=filters.created_from)
        if filters.created_to:
            queryset = queryset.filter(created_at__date__lte=filters.created_to)
        total = queryset.count()
        start = page_request.offset
        models = queryset.prefetch_related("items").order_by("created_at", "order_number")[
            start : start + page_request.size
        ]
        return Page([_to_domain(m) for m in models], total, page_request)

    def pending_ids(self) -> frozenset[UUID]:
        return frozenset(
            WorkOrderModel.objects.filter(status=WorkOrderModel.Status.PENDING).values_list(
                "pk", flat=True
            )
        )

    def many(self, work_order_ids: frozenset[UUID], *, lock: bool = False) -> list[WorkOrder]:
        if not work_order_ids:
            return []
        queryset = WorkOrderModel.objects.filter(pk__in=work_order_ids)
        if lock:
            # Locks only the O.T. rows (``of=("self",)``), in a fixed order to avoid deadlocks.
            list(queryset.select_for_update(of=("self",)).order_by("pk").values_list("pk"))
        models = queryset.prefetch_related("items").order_by("created_at", "order_number")
        return [_to_domain(m) for m in models]

    def active_for_quotation(self, quotation_id: UUID) -> WorkOrder | None:
        model = (
            WorkOrderModel.objects.prefetch_related("items")
            .filter(_ACTIVE, quotation_id=quotation_id)
            .first()
        )
        return _to_domain(model) if model else None

    def reconciled_since(self, dispatched_since: date, product_ids: list[UUID]) -> list[WorkOrder]:
        with_products = WorkOrderItemModel.objects.filter(product_id__in=product_ids).values(
            "work_order_id"
        )
        models = WorkOrderModel.objects.prefetch_related("items").filter(
            status=WorkOrderModel.Status.RECONCILED,
            actual_dispatch_date__gte=dispatched_since,
            pk__in=with_products,
        )
        return [_to_domain(m) for m in models]

    def for_customer(self, customer_id: UUID, page_request: PageRequest) -> Page[WorkOrder]:
        queryset = WorkOrderModel.objects.filter(customer_id=customer_id)
        total = queryset.count()
        start = page_request.offset
        models = queryset.prefetch_related("items").order_by("-created_at", "-order_number")[
            start : start + page_request.size
        ]
        return Page([_to_domain(m) for m in models], total, page_request)

    def quotations_with_active_order(self) -> frozenset[UUID]:
        return frozenset(
            WorkOrderModel.objects.filter(_ACTIVE).values_list("quotation_id", flat=True)
        )


class DjangoWorkOrderNumberGenerator(WorkOrderNumberGenerator):
    def next_number(self, created_at: datetime) -> str:
        with transaction.atomic():
            counter, _ = WorkOrderCounterModel.objects.select_for_update().get_or_create(
                pk=WorkOrderCounterModel.SINGLETON
            )
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
        return document_number(WORK_ORDER_PREFIX, created_at, counter.last_number)
