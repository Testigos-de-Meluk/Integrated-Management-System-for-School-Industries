"""Work order rules without a database (corrections README, summary item 17)."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from modules.shared_kernel.domain.exceptions import ValidationError
from modules.work_orders.domain.exceptions import (
    InvalidWorkOrderTransition,
    WorkOrderNotEditable,
)
from modules.work_orders.domain.work_order import (
    WorkOrder,
    WorkOrderCustomer,
    WorkOrderItem,
    WorkOrderStatus,
)

NOW = datetime(2026, 11, 27, 15, tzinfo=UTC)
TODAY = date(2026, 11, 27)
SCHOOL = WorkOrderCustomer(uuid4(), "800197268-4", "Colegio Los Robles SAS")


def item(quantity=10):
    return WorkOrderItem(uuid4(), "SIL-001", "Silla escolar", "Unidad", quantity)


def order(**overrides):
    values = {
        "number": "OT-20261127-00001",
        "quotation_id": uuid4(),
        "quotation_number": "COT-20261120-00004",
        "customer": SCHOOL,
        "items": [item()],
        "agreed_delivery_date": TODAY + timedelta(days=10),
        "today": TODAY,
        "now": NOW,
        "by_id": uuid4(),
        "by_name": "Olga Operadora",
    } | overrides
    return WorkOrder.generate(**values)


def test_generated_orders_start_pending():
    generated = order()
    assert generated.status is WorkOrderStatus.PENDING
    assert generated.is_editable and generated.is_active and not generated.was_exported


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"items": []}, "items"),
        ({"items": [item(0)]}, "items"),
        ({"agreed_delivery_date": None}, "agreed_delivery_date"),
        ({"agreed_delivery_date": TODAY - timedelta(days=1)}, "agreed_delivery_date"),
    ],
)
def test_generation_validates_items_and_the_agreed_date(overrides, field):
    with pytest.raises(ValidationError) as error:
        order(**overrides)
    assert field in error.value.errors


def test_the_full_cycle_with_the_real_dispatch_date():
    work_order = order()
    work_order.mark_registered_in_accounting()  # only the export does this
    assert work_order.was_exported and not work_order.is_editable

    with pytest.raises(ValidationError):
        work_order.reconcile(TODAY + timedelta(days=1), TODAY)  # future
    with pytest.raises(ValidationError):
        work_order.reconcile(TODAY - timedelta(days=1), TODAY)  # before the O.T. existed
    work_order.reconcile(TODAY, TODAY)

    assert work_order.status is WorkOrderStatus.RECONCILED
    assert work_order.actual_dispatch_date == TODAY


def test_no_jumps_between_statuses():
    work_order = order()
    with pytest.raises(InvalidWorkOrderTransition):
        work_order.reconcile(TODAY, TODAY)  # Pendiente → Conciliada is not allowed
    work_order.mark_registered_in_accounting()
    with pytest.raises(InvalidWorkOrderTransition):
        work_order.mark_registered_in_accounting()


def test_only_pending_orders_can_be_edited():
    work_order = order()
    work_order.update(SCHOOL, [item(5), item(7)], TODAY + timedelta(days=3), TODAY)
    assert [i.quantity for i in work_order.items] == [5, 7]

    work_order.mark_registered_in_accounting()
    with pytest.raises(WorkOrderNotEditable):
        work_order.update(SCHOOL, [item()], TODAY + timedelta(days=3), TODAY)


def test_an_unchanged_past_date_does_not_block_other_edits():
    work_order = order()
    later = TODAY + timedelta(days=20)  # the agreed date has passed meanwhile
    work_order.update(SCHOOL, [item(3)], work_order.agreed_delivery_date, later)
    with pytest.raises(ValidationError):
        work_order.update(SCHOOL, [item(3)], TODAY + timedelta(days=1), later)


@pytest.mark.parametrize("exported", [False, True])
def test_any_order_but_an_annulled_one_can_be_annulled_with_a_reason(exported):
    work_order = order()
    if exported:
        work_order.mark_registered_in_accounting()
        work_order.reconcile(TODAY, TODAY)
    with pytest.raises(ValidationError):
        work_order.cancel("  ")

    work_order.cancel("El cliente desistió del pedido")

    assert work_order.status is WorkOrderStatus.CANCELLED and not work_order.is_active
    with pytest.raises(InvalidWorkOrderTransition):
        work_order.cancel("otra vez")
