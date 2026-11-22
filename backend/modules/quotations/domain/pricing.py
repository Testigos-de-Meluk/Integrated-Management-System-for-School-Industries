"""Statistical price range from historical unit prices (fallback strategy of FR-02-05)."""

from decimal import Decimal
from statistics import quantiles

from modules.shared_kernel.domain.money import PriceRange

MIN_SAMPLES_FOR_PERCENTILES = 3


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
