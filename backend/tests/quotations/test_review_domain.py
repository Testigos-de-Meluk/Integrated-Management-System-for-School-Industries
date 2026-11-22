"""Review rules of the quotation aggregate (US 2.13, US 2.27 … US 2.29), without a database."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from modules.quotations.domain.exceptions import (
    ApprovalIncomplete,
    InvalidQuotationItems,
    QuotationLocked,
)
from modules.quotations.domain.quotation import (
    DispatchDateSource,
    Quotation,
    QuotationItem,
    QuotationStatus,
    RequesterContact,
)
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.money import PriceRange

NOW = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)
TODAY = NOW.date()
LATER = TODAY + timedelta(days=20)


def line(quantity=10, price_range=None, final=None):
    return QuotationItem(uuid4(), "SIL-001", "Silla", "Unidad", quantity, price_range, final)


def quotation(*items, suggested: date | None = None) -> Quotation:
    requester = RequesterContact.create("Laura Méndez", "laura@colegio.edu.co", "310 456 7890")
    return Quotation.request(
        "COT-2026-0001",
        requester,
        list(items) or [line(price_range=PriceRange(Decimal(100), Decimal(120)))],
        NOW,
        "key",
        suggested_dispatch_date=suggested,
    )


def approve(q: Quotation, prices=None, dispatch=LATER, when=NOW):
    q.approve(prices or {}, dispatch, "Pago a 30 días", uuid4(), "Ana Admin", when)


def test_modify_replaces_items_and_marks_it_modified():
    q = quotation()
    q.modify([line(5, final=Decimal("150000.4"))], "  Entrega en sede  ", LATER, TODAY)

    assert q.status is QuotationStatus.MODIFIED
    assert q.items[0].final_unit_price == Decimal(150000)  # whole pesos
    assert q.commercial_terms == "Entrega en sede"
    assert (q.estimated_dispatch_date, q.dispatch_date_source) == (LATER, DispatchDateSource.MANUAL)


@pytest.mark.parametrize(
    "items, error",
    [
        ([], InvalidQuotationItems),  # US 2.28.5: removing every product
        ([line(0)], InvalidQuotationItems),
        ([line(final=Decimal(0))], InvalidQuotationItems),
    ],
)
def test_modify_rejects_invalid_items(items, error):
    with pytest.raises(error):
        quotation().modify(items, "", None, TODAY)


def test_dispatch_date_cannot_be_in_the_past_and_a_confirmed_suggestion_stays_suggested():
    q = quotation(suggested=LATER)
    with pytest.raises(ValidationError) as error:
        q.modify(list(q.items), "", TODAY - timedelta(days=1), TODAY)
    assert "dispatch_date" in error.value.errors

    q.modify(list(q.items), "", LATER, TODAY)  # US 2.12: confirmed as is
    assert q.dispatch_date_source is DispatchDateSource.SUGGESTED


def test_approval_requires_every_final_price_and_a_dispatch_date():
    first, second = line(price_range=PriceRange(Decimal(100), Decimal(120))), line()
    q = quotation(first, second)

    with pytest.raises(ApprovalIncomplete) as error:
        approve(q, {first.id: Decimal(110)}, dispatch=None)
    assert set(error.value.errors) == {"items", "dispatch_date"}
    assert q.status is QuotationStatus.PENDING_REVIEW  # nothing changed


def test_approve_sets_final_prices_totals_approver_and_new_validity():
    first, second = line(4), line(2, final=Decimal(500))
    q = quotation(first, second)
    approve(q, {first.id: Decimal(1000)}, when=NOW + timedelta(days=3))

    assert q.status is QuotationStatus.APPROVED
    assert q.final_total == Decimal(4 * 1000 + 2 * 500)
    assert q.approved_by_name == "Ana Admin" and q.approved_at == NOW + timedelta(days=3)
    assert q.valid_until == TODAY + timedelta(days=3 + 15)
    snapshot_item = q.snapshot()["items"][0]
    assert snapshot_item["final_unit_price"] == "1000"  # audited next to the estimate (RN-M2-02)


def test_prices_of_items_from_another_quotation_are_rejected():
    with pytest.raises(InvalidQuotationItems):
        approve(quotation(line(final=Decimal(1))), {uuid4(): Decimal(10)})


def test_reject_requires_a_reason_and_is_final():
    q = quotation()
    with pytest.raises(ValidationError):
        q.reject("   ")
    q.reject("Fuera de la zona de despacho")

    assert q.status is QuotationStatus.REJECTED
    for action in (
        lambda: q.modify([line()], "", None, TODAY),
        lambda: approve(q),
        lambda: q.reject("otra vez"),
        lambda: q.link_customer(uuid4()),
    ):
        with pytest.raises(QuotationLocked):
            action()


def test_approved_is_immutable_but_a_missing_customer_can_be_linked_once():
    q = quotation(line(final=Decimal(1)))
    approve(q)
    with pytest.raises(QuotationLocked):
        q.modify([line()], "", None, TODAY)
    with pytest.raises(QuotationLocked):
        q.reject("No")

    customer = uuid4()
    q.link_customer(customer)  # needed to generate the work order (US 2.37)
    assert q.customer_id == customer
    with pytest.raises(QuotationLocked):
        q.link_customer(uuid4())
