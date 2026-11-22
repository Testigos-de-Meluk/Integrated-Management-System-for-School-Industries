"""Estimated prices (FR-02-05, RN-M2-01): always a range, and where it came from."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from statistics import quantiles

from modules.shared_kernel.domain.money import PriceRange

MIN_SAMPLES_FOR_PERCENTILES = 3


class PriceSource(StrEnum):
    HISTORY = "HISTORY"  # statistics of this product's own approved prices
    AI = "AI"  # AI estimate based on approved prices of similar products


@dataclass(frozen=True, slots=True)
class PriceEstimate:
    range: PriceRange
    source: PriceSource


def range_from_samples(samples: list[Decimal]) -> PriceRange | None:
    """Interquartile range (25th–75th percentiles) of past unit prices.

    With fewer than 3 samples, the lowest and highest observed prices are used; with none there is
    no estimate and the line is shown as "Precio por confirmar".
    """
    values = sorted(samples)
    if not values:
        return None
    if len(values) < MIN_SAMPLES_FOR_PERCENTILES:
        return PriceRange(values[0], values[-1])
    q1, _, q3 = quantiles(values, n=4, method="inclusive")
    return PriceRange(Decimal(q1), Decimal(q3))
