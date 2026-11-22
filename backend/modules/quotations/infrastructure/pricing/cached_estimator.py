"""Caches the estimates of a slow strategy (the AI) per product in the Django cache (Redis).

The public assistant recomputes the estimate every time a quantity changes: without a cache each
change would be a new AI call. Products the strategy could not price are cached too, so they are
not asked again until the entry expires. Failures (exceptions) are not cached.
"""

from decimal import Decimal
from uuid import UUID

from django.core.cache import cache

from modules.quotations.domain.pricing import PriceEstimate, PriceSource
from modules.quotations.ports.outbound.ports import PriceEstimator, PriceRequest
from modules.shared_kernel.domain.money import PriceRange

_NONE = "none"


class CachedPriceEstimator(PriceEstimator):
    def __init__(self, inner: PriceEstimator, ttl_seconds: int, prefix: str) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._prefix = prefix

    def _key(self, product_id: UUID) -> str:
        return f"{self._prefix}:{product_id}"

    def estimate(self, requests: list[PriceRequest]) -> dict[UUID, PriceEstimate]:
        result: dict[UUID, PriceEstimate] = {}
        missing: list[PriceRequest] = []
        cached = cache.get_many([self._key(pid) for pid, _ in requests])
        for product_id, quantity in requests:
            value = cached.get(self._key(product_id))
            if value is None:
                missing.append((product_id, quantity))
            elif value != _NONE:
                low, high, source = value
                result[product_id] = PriceEstimate(
                    PriceRange(Decimal(low), Decimal(high)), PriceSource(source)
                )
        if missing:
            found = self._inner.estimate(missing)
            result.update(found)
            cache.set_many(
                {
                    self._key(pid): (
                        (str(found[pid].range.min), str(found[pid].range.max), found[pid].source)
                        if pid in found
                        else _NONE
                    )
                    for pid, _ in missing
                },
                self._ttl,
            )
        return result
