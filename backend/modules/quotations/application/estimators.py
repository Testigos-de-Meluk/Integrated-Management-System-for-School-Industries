"""Price estimation strategies (Strategy pattern, NFR-05-01).

``FallbackPriceEstimator`` tries each strategy in order and returns the first estimate. Sub-step 4c
adds the AI strategy in front; the statistical one always remains as the fallback, so a request
never fails because the AI is unavailable.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from modules.quotations.domain.pricing import range_from_samples
from modules.quotations.ports.outbound.ports import PriceEstimator, PriceHistory
from modules.shared_kernel.domain.money import PriceRange

DEFAULT_LOOKBACK_DAYS = 365


class StatisticalPriceEstimator(PriceEstimator):
    """Interquartile range of the final unit prices approved in the last year."""

    def __init__(
        self,
        history: PriceHistory,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._history = history
        self._lookback = timedelta(days=lookback_days)
        self._now = clock

    def estimate(self, product_id: UUID, quantity: int) -> PriceRange | None:
        samples = self._history.approved_unit_prices(product_id, self._now() - self._lookback)
        return range_from_samples(samples)


class FallbackPriceEstimator(PriceEstimator):
    def __init__(self, strategies: list[PriceEstimator]) -> None:
        self._strategies = strategies

    def estimate(self, product_id: UUID, quantity: int) -> PriceRange | None:
        for strategy in self._strategies:
            try:
                result = strategy.estimate(product_id, quantity)
            except Exception:  # noqa: BLE001 — a failing strategy must not break the request
                result = None
            if result is not None:
                return result
        return None
