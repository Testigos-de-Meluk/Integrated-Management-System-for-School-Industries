"""Pure domain tests: money, statistical pricing and the quotation aggregate."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from modules.quotations.domain.exceptions import InvalidQuotationItems
from modules.quotations.domain.pricing import range_from_samples
from modules.quotations.domain.quotation import (
    Quotation,
    QuotationItem,
    QuotationStatus,
    RequesterContact,
)
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.money import PriceRange

NOW = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)


def item(quantity=10, price_range=None):
    return QuotationItem(uuid4(), "SIL-001", "Silla escolar", "Unidad", quantity, price_range)


def contact():
    return RequesterContact.create("Laura Méndez", "Laura@Colegio.edu.co", "310 456 7890")


def test_price_range_arithmetic_and_rounding():
    unit = PriceRange(Decimal("175000.4"), Decimal("195000.6"))

    assert (unit.min, unit.max) == (Decimal("175000"), Decimal("195001"))
    assert unit.times(40) == PriceRange(Decimal("7000000"), Decimal("7800040"))
    with pytest.raises(ValidationError):
        PriceRange(Decimal("10"), Decimal("5"))


@pytest.mark.parametrize(
    "samples, expected",
    [
        ([], None),
        ([Decimal("180000")], PriceRange(Decimal("180000"), Decimal("180000"))),
        ([Decimal("190000"), Decimal("170000")], PriceRange(Decimal("170000"), Decimal("190000"))),
        (
            [Decimal(v) for v in (160000, 170000, 180000, 190000, 200000)],
            PriceRange(Decimal("170000"), Decimal("190000")),
        ),
    ],
)
def test_range_from_samples_uses_the_interquartile_range(samples, expected):
    assert range_from_samples(samples) == expected


def test_requester_contact_is_validated_and_normalized():
    requester = contact()
    assert requester.email == "laura@colegio.edu.co" and requester.institution == ""

    with pytest.raises(ValidationError) as error:
        RequesterContact.create("", "no-email", "abc", tax_id="NIT<script>")
    assert set(error.value.errors) == {"full_name", "email", "phone", "tax_id"}


def test_request_creates_a_pending_quotation_with_partial_totals():
    quotation = Quotation.request(
        "COT-2026-0001",
        contact(),
        [item(40, PriceRange(Decimal(175000), Decimal(195000))), item(10, None)],
        NOW,
        access_key="k",
    )

    assert quotation.status is QuotationStatus.PENDING_REVIEW
    assert quotation.valid_until == date(2026, 12, 7)  # 15 days
    assert quotation.estimated_total == PriceRange(Decimal(7000000), Decimal(7800000))
    assert quotation.unpriced_items == 1
    assert quotation.estimated_dispatch_date is None


def test_request_rejects_empty_or_invalid_quantities():
    with pytest.raises(InvalidQuotationItems):
        Quotation.request("COT-2026-0001", contact(), [], NOW, access_key="k")
    with pytest.raises(InvalidQuotationItems):
        Quotation.request("COT-2026-0001", contact(), [item(0)], NOW, access_key="k")
