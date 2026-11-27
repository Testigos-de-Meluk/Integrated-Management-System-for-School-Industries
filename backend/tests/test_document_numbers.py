"""Document numbers (summary item 16 of the corrections) and the quotation renumbering."""

import importlib
from datetime import UTC, date, datetime, timedelta

import pytest
from django.apps import apps

from modules.quotations.infrastructure.models import QuotationCounterModel, QuotationModel
from modules.quotations.infrastructure.persistence.repositories import (
    DjangoQuotationNumberGenerator,
)
from modules.shared_kernel.domain.document_numbers import business_date, document_number

renumber = importlib.import_module(
    "modules.quotations.infrastructure.migrations.0004_global_quotation_numbers"
).renumber


def test_the_date_is_the_colombian_one():
    late_evening = datetime(2026, 11, 28, 2, 30, tzinfo=UTC)  # 21:30 of the 27th in Bogotá
    assert business_date(late_evening) == date(2026, 11, 27)
    assert document_number("OT", late_evening, 42) == "OT-20261127-00042"
    assert document_number("COT", late_evening, 123456) == "COT-20261127-123456"  # just grows
    with pytest.raises(ValueError):
        document_number("OT", late_evening, 0)


@pytest.mark.django_db
def test_the_counter_is_global_and_never_restarts():
    numbers = DjangoQuotationNumberGenerator()
    first = numbers.next_number(datetime(2026, 12, 31, 15, tzinfo=UTC))
    second = numbers.next_number(datetime(2027, 1, 2, 15, tzinfo=UTC))
    assert (first, second) == ("COT-20261231-00001", "COT-20270102-00002")


def quotation(number, issued_at):
    return QuotationModel.objects.create(
        quotation_number=number,
        issued_at=issued_at,
        requester_full_name="X",
        requester_email="x@x.co",
        requester_phone="3000000000",
        valid_until=issued_at.date(),
    )


@pytest.mark.django_db
def test_renumbering_on_an_empty_database_only_creates_the_counter():
    QuotationCounterModel.objects.all().delete()
    renumber(apps, None)
    assert QuotationCounterModel.objects.get().last_number == 0


@pytest.mark.django_db
def test_renumbering_follows_issue_order_and_leaves_the_counter_at_the_last_number():
    start = datetime(2026, 11, 20, 23, 30, tzinfo=UTC)  # 18:30 in Bogotá
    late = quotation("COT-2026-0002", start + timedelta(hours=2))  # 20:30 of the 20th in Bogotá
    early = quotation("COT-2026-0001", start)

    renumber(apps, None)
    renumber(apps, None)  # running it again changes nothing

    early.refresh_from_db()
    late.refresh_from_db()
    assert early.quotation_number == "COT-20261120-00001"
    assert late.quotation_number == "COT-20261120-00002"
    assert DjangoQuotationNumberGenerator().next_number(start).endswith("-00003")
