"""Suggested dispatch date by median (FR-02-06 corrected, step 5b decisions)."""

from datetime import date
from uuid import uuid4

import pytest

from modules.quotations.application.dispatch_estimator import (
    MedianDispatchDateEstimator,
    quantity_bucket,
    rounded_up_median,
)
from modules.quotations.ports.outbound.ports import DispatchLeadTime, DispatchSamples
from modules.shared_kernel.domain.business_days import add_business_days

TODAY = date(2026, 11, 27)  # Friday
APPROVED = date(2026, 11, 2)  # Monday, a holiday: lead times count business days after it
CHAIR, DESK = uuid4(), uuid4()


class FixedSamples(DispatchSamples):
    def __init__(self, *samples):
        self.samples = list(samples)
        self.asked = []

    def lead_times(self, product_ids, dispatched_since):
        self.asked.append(dispatched_since)
        return [s for s in self.samples if s.product_id in product_ids]


def dispatched(product, quantity, business_days):
    """A line approved on APPROVED and dispatched that many business days later."""
    return DispatchLeadTime(product, quantity, APPROVED, add_business_days(APPROVED, business_days))


@pytest.mark.parametrize(
    ("quantity", "bucket"), [(1, 0), (10, 0), (11, 1), (50, 1), (51, 2), (100, 2), (101, 3)]
)
def test_quantity_buckets(quantity, bucket):
    assert quantity_bucket(quantity) == bucket


def test_an_even_median_is_rounded_up():
    assert rounded_up_median([10, 13]) == 12  # 11.5 → 12: better a day late than early
    assert rounded_up_median([4, 9, 5]) == 5


def test_median_in_business_days_from_today():
    samples = FixedSamples(*(dispatched(CHAIR, 40, d) for d in (8, 10, 12)))
    estimator = MedianDispatchDateEstimator(samples)

    suggested = estimator.suggest([(CHAIR, 35)], TODAY)

    assert suggested == add_business_days(TODAY, 10) == date(2026, 12, 14)
    assert samples.asked == [date(2025, 11, 27)]  # last 365 days only


def test_needs_three_samples_in_the_same_bucket():
    samples = FixedSamples(
        dispatched(CHAIR, 40, 8),
        dispatched(CHAIR, 45, 10),
        dispatched(CHAIR, 5, 3),  # another bucket (1–10): does not count for 40 units
    )
    assert MedianDispatchDateEstimator(samples).suggest([(CHAIR, 40)], TODAY) is None


def test_several_products_take_the_largest_median_or_nothing():
    chairs = [dispatched(CHAIR, 20, d) for d in (5, 6, 7)]
    desks = [dispatched(DESK, 20, d) for d in (12, 15, 20)]
    estimator = MedianDispatchDateEstimator(FixedSamples(*chairs, *desks))

    assert estimator.suggest([(CHAIR, 20), (DESK, 20)], TODAY) == add_business_days(TODAY, 15)
    # One product without enough history → no suggestion at all (no underestimate).
    estimator = MedianDispatchDateEstimator(FixedSamples(*chairs))
    assert estimator.suggest([(CHAIR, 20), (DESK, 20)], TODAY) is None
