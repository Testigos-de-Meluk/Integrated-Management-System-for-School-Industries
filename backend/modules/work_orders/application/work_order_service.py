"""Work order use cases (implements ``WorkOrderManagement``): FR-02-19 … FR-02-23, step 5 version.

Every use case requires ``WORK_ORDER_MANAGE``. Other modules are reached only through their inbound
ports: approved quotations (quotations), customers and the product catalog.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import UUID

from modules.customers.ports.inbound.customer_directory import CustomerDirectory, CustomerSummary
from modules.products.ports.inbound.product_catalog import ProductCatalog
from modules.quotations.ports.inbound.approved_quotations import (
    ApprovedQuotations,
    ApprovedQuotationView,
)
from modules.shared_kernel.domain.audit import AuditAction, AuditRecord
from modules.shared_kernel.domain.document_numbers import business_date
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger
from modules.shared_kernel.ports.outbound.event_publisher import EventPublisher
from modules.work_orders.domain.events import WorkOrderCancelled, WorkOrderGenerated
from modules.work_orders.domain.exceptions import ActiveWorkOrderExists, WorkOrderNotFound
from modules.work_orders.domain.work_order import (
    WorkOrder,
    WorkOrderCustomer,
    WorkOrderItem,
    WorkOrderStatus,
)
from modules.work_orders.ports.inbound.work_order_management import (
    AvailableQuotationView,
    GenerateWorkOrderCommand,
    UpdateWorkOrderCommand,
    WorkOrderDetailView,
    WorkOrderFilters,
    WorkOrderItemInput,
    WorkOrderItemView,
    WorkOrderManagement,
    WorkOrderSummaryView,
)
from modules.work_orders.ports.outbound.ports import WorkOrderNumberGenerator, WorkOrderRepository

CUSTOMER_REQUIRED = "Seleccione o registre un cliente activo para la orden de trabajo."
ONLY_ACTIVE_PRODUCTS = "Solo puede agregar productos activos del catálogo."


def _items_view(items) -> tuple[WorkOrderItemView, ...]:
    return tuple(
        WorkOrderItemView(
            i.product_id, i.product_code, i.description, i.unit_of_measure, i.quantity
        )
        for i in items
    )


def summary_view(order: WorkOrder) -> WorkOrderSummaryView:
    return WorkOrderSummaryView(
        id=order.id,
        number=order.number,
        quotation_id=order.quotation_id,
        quotation_number=order.quotation_number,
        customer_id=order.customer.id,
        customer_tax_id=order.customer.tax_id,
        customer_name=order.customer.name,
        items=_items_view(order.items),
        agreed_delivery_date=order.agreed_delivery_date,
        status=order.status.value,
        created_at=order.created_at,
    )


def detail_view(order: WorkOrder) -> WorkOrderDetailView:
    return WorkOrderDetailView(
        id=order.id,
        number=order.number,
        quotation_id=order.quotation_id,
        quotation_number=order.quotation_number,
        customer_id=order.customer.id,
        customer_tax_id=order.customer.tax_id,
        customer_name=order.customer.name,
        items=_items_view(order.items),
        agreed_delivery_date=order.agreed_delivery_date,
        actual_dispatch_date=order.actual_dispatch_date,
        status=order.status.value,
        cancellation_reason=order.cancellation_reason,
        created_at=order.created_at,
        created_by_name=order.created_by_name,
        can_edit=order.is_editable,
        can_reconcile=order.status is WorkOrderStatus.REGISTERED_IN_SIIGO,
        can_cancel=order.is_active,
        was_exported=order.was_exported,
    )


class WorkOrderService(WorkOrderManagement):
    def __init__(
        self,
        repository: WorkOrderRepository,
        numbers: WorkOrderNumberGenerator,
        quotations: ApprovedQuotations,
        customers: CustomerDirectory,
        catalog: ProductCatalog,
        events: EventPublisher,
        audit_logger: AuditLogger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._numbers = numbers
        self._quotations = quotations
        self._customers = customers
        self._catalog = catalog
        self._events = events
        self._audit = audit_logger
        self._now = clock

    # --- Queries ------------------------------------------------------------------------------

    def list_work_orders(
        self, actor: Actor, filters: WorkOrderFilters, page_request: PageRequest
    ) -> Page[WorkOrderSummaryView]:
        actor.require(Permission.WORK_ORDER_MANAGE)
        if filters.agreed_from and filters.agreed_to and filters.agreed_from > filters.agreed_to:
            raise ValidationError.for_field(
                "agreed_to", "La fecha final no puede ser anterior a la inicial."
            )
        page = self._repository.search(filters, page_request)
        return Page([summary_view(o) for o in page.items], page.total, page.request)

    def get_work_order(self, actor: Actor, work_order_id: UUID) -> WorkOrderDetailView:
        actor.require(Permission.WORK_ORDER_MANAGE)
        return detail_view(self._get_or_fail(work_order_id))

    def available_quotations(
        self, actor: Actor, text: str | None, page_request: PageRequest
    ) -> Page[AvailableQuotationView]:
        actor.require(Permission.WORK_ORDER_MANAGE)
        page = self._quotations.search_approved(
            actor, text, self._repository.quotations_with_active_order(), page_request
        )
        return Page([self._available(q) for q in page.items], page.total, page.request)

    # --- Commands -----------------------------------------------------------------------------

    def generate(self, actor: Actor, command: GenerateWorkOrderCommand) -> WorkOrderDetailView:
        actor.require(Permission.WORK_ORDER_MANAGE)
        quotation = self._quotations.get_approved(actor, command.quotation_id)
        active = self._repository.active_for_quotation(quotation.id)
        if active is not None:
            raise ActiveWorkOrderExists(active.number)

        customer = self._customer_for(quotation, command.customer_id)
        now = self._now()
        order = WorkOrder.generate(
            number=self._numbers.next_number(now),
            quotation_id=quotation.id,
            quotation_number=quotation.number,
            quotation_approved_at=quotation.approved_at,
            customer=WorkOrderCustomer(customer.id, customer.tax_id, customer.name),
            items=[
                WorkOrderItem(
                    i.product_id, i.product_code, i.description, i.unit_of_measure, i.quantity
                )
                for i in quotation.items
            ],
            agreed_delivery_date=command.agreed_delivery_date or quotation.dispatch_date,
            today=business_date(now),
            now=now,
            by_id=actor.user_id,
            by_name=actor.display_name or actor.role.value,
        )
        if quotation.customer_id is None:
            # The customer chosen here also belongs to the quotation (FR-02-15, US 2.37.2).
            self._quotations.link_customer(actor, quotation.id, customer.id)
        self._repository.add(order)
        self._log(AuditAction.CREATED, actor, order, None)
        self._events.publish(
            WorkOrderGenerated(
                work_order_id=order.id,
                number=order.number,
                quotation_id=order.quotation_id,
                occurred_at=now,
            )
        )
        return detail_view(order)

    def update(
        self, actor: Actor, work_order_id: UUID, command: UpdateWorkOrderCommand
    ) -> WorkOrderDetailView:
        actor.require(Permission.WORK_ORDER_MANAGE)
        order = self._get_or_fail(work_order_id)
        before = order.snapshot()
        customer = order.customer
        if command.customer_id != customer.id:
            chosen = self._active_customer(command.customer_id)
            customer = WorkOrderCustomer(chosen.id, chosen.tax_id, chosen.name)
        order.update(
            customer,
            self._edited_items(order, command.items),
            command.agreed_delivery_date,
            business_date(self._now()),
        )
        self._repository.update(order)
        self._log(AuditAction.UPDATED, actor, order, before)
        return detail_view(order)

    def cancel(self, actor: Actor, work_order_id: UUID, reason: str) -> WorkOrderDetailView:
        actor.require(Permission.WORK_ORDER_MANAGE)
        order = self._get_or_fail(work_order_id)
        before = order.snapshot()
        order.cancel(reason)
        self._repository.update(order)
        self._log(AuditAction.CANCELLED, actor, order, before, order.cancellation_reason)
        self._events.publish(
            WorkOrderCancelled(work_order_id=order.id, number=order.number, occurred_at=self._now())
        )
        return detail_view(order)

    def reconcile(
        self, actor: Actor, work_order_id: UUID, actual_dispatch_date: date
    ) -> WorkOrderDetailView:
        actor.require(Permission.WORK_ORDER_MANAGE)
        order = self._get_or_fail(work_order_id)
        before = order.snapshot()
        order.reconcile(actual_dispatch_date, business_date(self._now()))
        self._repository.update(order)
        self._log(AuditAction.STATUS_CHANGED, actor, order, before)
        return detail_view(order)

    # --- Helpers ------------------------------------------------------------------------------

    def _get_or_fail(self, work_order_id: UUID) -> WorkOrder:
        order = self._repository.get(work_order_id)
        if order is None:
            raise WorkOrderNotFound()
        return order

    def _active_customer(self, customer_id: UUID | None) -> CustomerSummary:
        customer = self._customers.by_id(customer_id) if customer_id else None
        if customer is None:
            raise ValidationError.for_field("customer_id", CUSTOMER_REQUIRED)
        if not customer.is_active:
            raise ValidationError.for_field(
                "customer_id",
                f"El cliente {customer.name} está inactivo. Reactívelo o elija otro cliente.",
            )
        return customer

    def _customer_for(
        self, quotation: ApprovedQuotationView, chosen_id: UUID | None
    ) -> CustomerSummary:
        if quotation.customer_id is None:
            return self._active_customer(chosen_id)
        if chosen_id is not None and chosen_id != quotation.customer_id:
            raise ValidationError.for_field(
                "customer_id",
                "La cotización ya tiene un cliente vinculado; la orden de trabajo usa ese cliente.",
            )
        return self._active_customer(quotation.customer_id)

    def _edited_items(
        self, order: WorkOrder, inputs: tuple[WorkOrderItemInput, ...]
    ) -> list[WorkOrderItem]:
        """Products already on the O.T. keep their snapshot (even if deactivated since); new
        products must be active in the catalog. Repeated products are merged."""
        merged: dict[UUID, int] = {}
        for line in inputs:
            merged[line.product_id] = merged.get(line.product_id, 0) + line.quantity
        current = {i.product_id: i for i in order.items}
        new_ids = [pid for pid in merged if pid not in current]
        catalog = self._catalog.selectable_by_ids(new_ids) if new_ids else {}
        if any(pid not in catalog for pid in new_ids):
            raise ValidationError.for_field("items", ONLY_ACTIVE_PRODUCTS)
        items = []
        for product_id, quantity in merged.items():
            if product_id in current:
                kept = current[product_id]
                items.append(
                    WorkOrderItem(
                        product_id,
                        kept.product_code,
                        kept.description,
                        kept.unit_of_measure,
                        quantity,
                        id=kept.id,
                    )
                )
            else:
                product = catalog[product_id]
                items.append(
                    WorkOrderItem(
                        product.id, product.code, product.name, product.unit_of_measure, quantity
                    )
                )
        return items

    def _available(self, quotation: ApprovedQuotationView) -> AvailableQuotationView:
        customer = self._customers.by_id(quotation.customer_id) if quotation.customer_id else None
        return AvailableQuotationView(
            id=quotation.id,
            number=quotation.number,
            approved_at=quotation.approved_at,
            requester_name=quotation.requester_name,
            requester_institution=quotation.requester_institution,
            requester_tax_id=quotation.requester_tax_id,
            customer_id=quotation.customer_id,
            customer_name=customer.name if customer else None,
            customer_active=customer.is_active if customer else None,
            dispatch_date=quotation.dispatch_date,
            items=tuple(
                WorkOrderItemView(
                    i.product_id, i.product_code, i.description, i.unit_of_measure, i.quantity
                )
                for i in quotation.items
            ),
        )

    def _log(
        self,
        action: AuditAction,
        actor: Actor,
        order: WorkOrder,
        before: dict | None,
        reason: str | None = None,
    ) -> None:
        self._audit.log(
            AuditRecord(
                action=action,
                entity_type="WorkOrder",
                entity_id=str(order.id),
                actor=actor,
                old_values=before,
                new_values=order.snapshot(),
                reason=reason,
            )
        )
