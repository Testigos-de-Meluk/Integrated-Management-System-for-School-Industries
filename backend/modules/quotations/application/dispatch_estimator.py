"""Suggested dispatch date from real dispatches (FR-02-06 corrected, step 5b decisions).

* Lead time of a past line = business days from the quotation approval to the real dispatch of
  its work order (reconciled, never annulled; product and quantity as dispatched).
* Median per product and quantity bucket (1–10, 11–50, 51–100, more than 100), over the last
  365 days. With an even number of samples, the mean of the two middle ones, rounded **up**.
* At least 3 samples per line; if any line has fewer there is no suggestion (taking the largest
  of the others would underestimate the date). With several products, the largest median wins.
* Suggested date = the given day + that many business days (Monday to Friday, no Colombian
  holidays). Median only: no extra days for absences or material shortages (RN-M2-05).
"""

import math
from datetime import date, timedelta
from statistics import median
from uuid import UUID

from modules.quotations.ports.outbound.ports import DispatchDateEstimator, DispatchSamples
from modules.shared_kernel.domain.business_days import add_business_days, business_days_between

MIN_SAMPLES = 3
LOOKBACK_DAYS = 365
#: Upper bound of each quantity bucket; ``None`` = no limit.
BUCKET_LIMITS: tuple[int | None, ...] = (10, 50, 100, None)


def quantity_bucket(quantity: int) -> int:
    """Index of the bucket the quantity falls in."""
    for index, limit in enumerate(BUCKET_LIMITS):
        if limit is None or quantity <= limit:
            return index
    raise AssertionError("unreachable")


def rounded_up_median(values: list[int]) -> int:
    return math.ceil(median(values))


class MedianDispatchDateEstimator(DispatchDateEstimator):
    """Strategy (NFR-05-01) that replaces the step-4 placeholder."""

    def __init__(self, samples: DispatchSamples, lookback_days: int = LOOKBACK_DAYS) -> None:
        self._samples = samples
        self._lookback = timedelta(days=lookback_days)

    def suggest(self, items: list[tuple[UUID, int]], today: date) -> date | None:
        if not items:
            return None
        product_ids = list({product_id for product_id, _ in items})
        lead_days: dict[tuple[UUID, int], list[int]] = {}
        for sample in self._samples.lead_times(product_ids, today - self._lookback):
            key = (sample.product_id, quantity_bucket(sample.quantity))
            days = business_days_between(sample.approved_on, sample.dispatched_on)
            lead_days.setdefault(key, []).append(days)

        medians = []
        for product_id, quantity in items:
            history = lead_days.get((product_id, quantity_bucket(quantity)), [])
            if len(history) < MIN_SAMPLES:
                return None  # "Sin datos históricos suficientes para estimar la fecha de despacho"
            medians.append(rounded_up_median(history))
        return add_business_days(today, max(medians))
