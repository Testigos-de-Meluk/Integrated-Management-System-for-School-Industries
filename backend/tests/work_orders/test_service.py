"""Work order use cases with in-memory fakes (US 2.35 … US 2.40, step 5 version)."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from modules.customers.ports.inbound.customer_directory import CustomerSummary
from modules.quotations.domain.exceptions import QuotationNotFound
from modules.quotations.ports.inbound.approved_quotations import (
    ApprovedItemView,
    ApprovedQuotations,
    ApprovedQuotationView,
)
from modules.shared_kernel.domain.audit import AuditAction
from modules.shared_kernel.domain.document_numbers import document_number
from modules.shared_kernel.domain.exceptions import PermissionDeniedError, ValidationError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, RoleType
from modules.work_orders.application.work_order_service import WorkOrderService
from modules.work_orders.domain.events import WorkOrderGenerated
from modules.work_orders.domain.exceptions import ActiveWorkOrderExists, WorkOrderNotEditable
from modules.work_orders.ports.inbound.work_order_management import (
    GenerateWorkOrderCommand,
    UpdateWorkOrderCommand,
    WorkOrderFilters,
    WorkOrderItemInput,
)
from modules.work_orders.ports.outbound.ports import WorkOrderNumberGenerator, WorkOrderRepository

from ..quotations.fakes import BOARD, CHAIR, DESK, FakeCatalog, FakeCustomers
from ..shared_fakes import SpyAuditLogger, SpyEventPublisher

NOW = datetime(2026, 11, 27, 15, tzinfo=UTC)  # 10:00 in Bogotá
TODAY = date(2026, 11, 27)
OPERATOR = Actor.for_role(RoleType.OPERATOR, user_id=uuid4(), display_name="Olga Operadora")
SCHOOL = CustomerSummary(uuid4(), "800197268-4", "Colegio Los Robles SAS", True)
OTHER = CustomerSummary(uuid4(), "900456789-1", "Colegio San José", True)
CLOSED = CustomerSummary(uuid4(), "860000123-1", "Colegio Cerrado", False)


class MemoryWorkOrders(WorkOrderRepository):
    def __init__(self):
        self.items = {}

    def add(self, work_order):
        if self.active_for_quotation(work_order.quotation_id):
            raise ActiveWorkOrderExists()
        self.items[work_order.id] = work_order

    def get(self, work_order_id):
        return self.items.get(work_order_id)

    def update(self, work_order):
        self.items[work_order.id] = work_order

    def search(self, filters, page_request):
        found = sorted(self.items.values(), key=lambda o: o.created_at, reverse=True)
        if filters.status:
            found = [o for o in found if o.status.value == filters.status]
        return Page(found, len(found), page_request)

    def active_for_quotation(self, quotation_id):
        return next(
            (o for o in self.items.values() if o.quotation_id == quotation_id and o.is_active),
            None,
        )

    def quotations_with_active_order(self):
        return frozenset(o.quotation_id for o in self.items.values() if o.is_active)

    def reconciled_since(self, dispatched_since, product_ids):
        return [
            o
            for o in self.items.values()
            if o.status.value == "RECONCILED"
            and o.actual_dispatch_date >= dispatched_since
            and any(i.product_id in product_ids for i in o.items)
        ]

    def for_customer(self, customer_id, page_request):
        found = [o for o in self.items.values() if o.customer.id == customer_id]
        return Page(found, len(found), page_request)

    def search_among(self, work_order_ids, filters, page_request):
        found = [o for o in self.items.values() if o.id in work_order_ids]
        return Page(found, len(found), page_request)

    def pending_ids(self):
        return frozenset(o.id for o in self.items.values() if o.status.value == "PENDING")


class Numbers(WorkOrderNumberGenerator):
    def __init__(self):
        self.last = 0

    def next_number(self, created_at):
        self.last += 1
        return document_number("OT", created_at, self.last)


class FakeApprovedQuotations(ApprovedQuotations):
    def __init__(self, *quotations):
        self.quotations = {q.id: q for q in quotations}
        self.linked = []

    def search_approved(self, actor, text, excluded_ids, page_request):
        found = [q for q in self.quotations.values() if q.id not in excluded_ids]
        return Page(found, len(found), page_request)

    def get_approved(self, actor, quotation_id):
        if quotation_id not in self.quotations:
            raise QuotationNotFound()
        return self.quotations[quotation_id]

    def link_customer(self, actor, quotation_id, customer_id):
        self.linked.append((quotation_id, customer_id))


def approved(customer_id=None, dispatch=TODAY + timedelta(days=15)):
    return ApprovedQuotationView(
        id=uuid4(),
        number="COT-20261120-00004",
        approved_at=NOW - timedelta(days=2),
        requester_name="Laura Méndez",
        requester_institution="Colegio Los Robles",
        requester_tax_id="800197268-4",
        customer_id=customer_id,
        dispatch_date=dispatch,
        items=(
            ApprovedItemView(CHAIR.id, CHAIR.code, CHAIR.name, "Unidad", 40),
            ApprovedItemView(DESK.id, DESK.code, DESK.name, "Unidad", 10),
        ),
    )


@pytest.fixture
def deps():
    return {
        "repository": MemoryWorkOrders(),
        "audit": SpyAuditLogger(),
        "events": SpyEventPublisher(),
        "with_customer": approved(SCHOOL.id),
        "without_customer": approved(None),
    }


@pytest.fixture
def service(deps):
    deps["quotations"] = FakeApprovedQuotations(deps["with_customer"], deps["without_customer"])
    return WorkOrderService(
        repository=deps["repository"],
        numbers=Numbers(),
        quotations=deps["quotations"],
        customers=FakeCustomers(SCHOOL, OTHER, CLOSED),
        catalog=FakeCatalog(),
        events=deps["events"],
        audit_logger=deps["audit"],
        clock=lambda: NOW,
    )


def test_generate_copies_the_quotation_numbers_it_audits_and_announces_it(service, deps):
    source = deps["with_customer"]
    order = service.generate(OPERATOR, GenerateWorkOrderCommand(source.id))

    assert order.number == "OT-20261127-00001" and order.status == "PENDING"
    assert order.customer_name == SCHOOL.name and order.quotation_number == source.number
    assert [(i.product_code, i.quantity) for i in order.items] == [("SIL-001", 40), ("MES-002", 10)]
    assert order.agreed_delivery_date == source.dispatch_date  # default
    assert order.created_by_name == "Olga Operadora"
    assert deps["audit"].records[0].action is AuditAction.CREATED
    event = deps["events"].events[0]
    assert isinstance(event, WorkOrderGenerated) and event.work_order_id == order.id


def test_a_quotation_without_customer_needs_one_and_gets_it_linked(service, deps):
    source = deps["without_customer"]
    with pytest.raises(ValidationError) as error:
        service.generate(OPERATOR, GenerateWorkOrderCommand(source.id))
    assert "customer_id" in error.value.errors
    with pytest.raises(ValidationError):  # inactive customers are refused
        service.generate(OPERATOR, GenerateWorkOrderCommand(source.id, CLOSED.id))

    order = service.generate(OPERATOR, GenerateWorkOrderCommand(source.id, OTHER.id))

    assert order.customer_id == OTHER.id
    assert deps["quotations"].linked == [(source.id, OTHER.id)]


def test_the_linked_customer_of_the_quotation_cannot_be_replaced(service, deps):
    source = deps["with_customer"]
    with pytest.raises(ValidationError):
        service.generate(OPERATOR, GenerateWorkOrderCommand(source.id, OTHER.id))


def test_one_active_order_per_quotation_but_a_new_one_after_annulling(service, deps):
    source = deps["with_customer"]
    first = service.generate(OPERATOR, GenerateWorkOrderCommand(source.id))
    with pytest.raises(ActiveWorkOrderExists) as error:
        service.generate(OPERATOR, GenerateWorkOrderCommand(source.id))
    assert first.number in error.value.message

    available = service.available_quotations(OPERATOR, None, PageRequest())
    assert [q.id for q in available.items] == [deps["without_customer"].id]

    service.cancel(OPERATOR, first.id, "Se generó con la fecha equivocada")
    second = service.generate(OPERATOR, GenerateWorkOrderCommand(source.id))
    assert second.number.endswith("-00002")


def test_a_past_dispatch_date_must_be_replaced(service, deps):
    late = approved(SCHOOL.id, dispatch=TODAY - timedelta(days=1))
    deps["quotations"].quotations[late.id] = late
    with pytest.raises(ValidationError) as error:
        service.generate(OPERATOR, GenerateWorkOrderCommand(late.id))
    assert "agreed_delivery_date" in error.value.errors
    ok = service.generate(OPERATOR, GenerateWorkOrderCommand(late.id, None, TODAY))
    assert ok.agreed_delivery_date == TODAY


def test_edit_keeps_snapshots_adds_active_products_and_audits(service, deps):
    order = service.generate(OPERATOR, GenerateWorkOrderCommand(deps["with_customer"].id))
    command = UpdateWorkOrderCommand(
        customer_id=OTHER.id,
        items=(
            WorkOrderItemInput(CHAIR.id, 20),
            WorkOrderItemInput(BOARD.id, 2),
            WorkOrderItemInput(CHAIR.id, 5),  # repeated: merged
        ),
        agreed_delivery_date=TODAY + timedelta(days=30),
    )

    edited = service.update(OPERATOR, order.id, command)

    assert edited.number == order.number  # never changes
    assert edited.customer_name == OTHER.name
    assert [(i.product_code, i.quantity) for i in edited.items] == [("SIL-001", 25), ("TAB-003", 2)]
    record = deps["audit"].records[-1]
    assert record.action is AuditAction.UPDATED
    assert record.old_values["customer"].endswith(SCHOOL.name)


def test_edit_refuses_inactive_products_and_customers(service, deps):
    order = service.generate(OPERATOR, GenerateWorkOrderCommand(deps["with_customer"].id))

    def update(customer_id=SCHOOL.id, product_id=CHAIR.id):
        items = (WorkOrderItemInput(product_id, 1),)
        later = TODAY + timedelta(days=5)
        return service.update(OPERATOR, order.id, UpdateWorkOrderCommand(customer_id, items, later))

    with pytest.raises(ValidationError):
        update(product_id=uuid4())  # not an active catalog product
    with pytest.raises(ValidationError):
        update(customer_id=CLOSED.id)


def test_exported_orders_are_read_only_and_reconcile_needs_the_real_date(service, deps):
    order = service.generate(OPERATOR, GenerateWorkOrderCommand(deps["with_customer"].id))
    deps["repository"].items[order.id].mark_registered_in_siigo()  # what the export will do

    with pytest.raises(WorkOrderNotEditable):
        service.update(
            OPERATOR,
            order.id,
            UpdateWorkOrderCommand(SCHOOL.id, (WorkOrderItemInput(CHAIR.id, 1),), TODAY),
        )
    reconciled = service.reconcile(OPERATOR, order.id, TODAY)

    assert reconciled.status == "RECONCILED" and reconciled.actual_dispatch_date == TODAY
    assert reconciled.can_cancel and reconciled.was_exported and not reconciled.can_edit
    assert deps["audit"].records[-1].action is AuditAction.STATUS_CHANGED


def test_annulment_is_audited_with_its_reason(service, deps):
    order = service.generate(OPERATOR, GenerateWorkOrderCommand(deps["with_customer"].id))
    annulled = service.cancel(OPERATOR, order.id, "El cliente desistió")
    record = deps["audit"].records[-1]
    assert annulled.status == "CANCELLED" and not annulled.can_cancel
    assert record.action is AuditAction.CANCELLED and record.reason == "El cliente desistió"


def test_permissions_and_filters(service, deps):
    no_access = Actor.for_role(RoleType.OPERATOR, user_id=uuid4())
    object.__setattr__(no_access, "permissions", frozenset())
    with pytest.raises(PermissionDeniedError):
        service.list_work_orders(no_access, WorkOrderFilters(), PageRequest())
    with pytest.raises(ValidationError):
        service.list_work_orders(
            OPERATOR,
            WorkOrderFilters(agreed_from=TODAY, agreed_to=TODAY - timedelta(days=1)),
            PageRequest(),
        )
