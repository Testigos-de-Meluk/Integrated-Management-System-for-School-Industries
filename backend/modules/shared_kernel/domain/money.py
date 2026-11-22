"""Money value objects (class diagram, Shared Kernel). Amounts are Colombian pesos (COP), kept as
``Decimal`` and rounded to whole pesos: there are no cents in practice."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .exceptions import ValidationError

CURRENCY = "COP"


def to_pesos(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class PriceRange:
    """Estimated price, never a fixed amount (RN-M2-01): from ``min`` to ``max``."""

    min: Decimal
    max: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "min", to_pesos(self.min))
        object.__setattr__(self, "max", to_pesos(self.max))
        if self.min < 0 or self.max < self.min:
            raise ValidationError.for_field("price", "El rango de precio no es válido.")

    def __add__(self, other: "PriceRange") -> "PriceRange":
        return PriceRange(self.min + other.min, self.max + other.max)

    def times(self, quantity: int) -> "PriceRange":
        return PriceRange(self.min * quantity, self.max * quantity)

    @property
    def midpoint(self) -> Decimal:
        return to_pesos((self.min + self.max) / 2)
