"""Outbound ports of the Quotations module."""

from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from modules.quotations.domain.quotation import Quotation
from modules.shared_kernel.domain.money import PriceRange


class QuotationRepository(ABC):
    @abstractmethod
    def add(self, quotation: Quotation) -> None: ...

    @abstractmethod
    def get(self, quotation_id: UUID) -> Quotation | None: ...


class QuotationNumberGenerator(ABC):
    """Consecutive human reference per year: COT-2026-0001, COT-2026-0002…"""

    @abstractmethod
    def next_number(self, year: int) -> str: ...


class PriceHistory(ABC):
    @abstractmethod
    def approved_unit_prices(self, product_id: UUID, since: datetime) -> list[Decimal]:
        """Final unit prices of APPROVED quotations since ``since`` (newest first)."""


class PriceEstimator(ABC):
    """Strategy (NFR-05-01): how a unit price range is estimated for a product."""

    @abstractmethod
    def estimate(self, product_id: UUID, quantity: int) -> PriceRange | None:
        """``None`` when there is not enough information ("Precio por confirmar")."""


class DispatchDateEstimator(ABC):
    """Strategy (NFR-05-01): suggested dispatch date from historical medians (FR-02-06)."""

    @abstractmethod
    def suggest(self, items: list[tuple[UUID, int]], today: date) -> date | None:
        """``None`` = "Sin datos históricos suficientes para estimar la fecha de despacho"."""


class QuotationDocumentGenerator(ABC):
    @abstractmethod
    def preliminary_pdf(self, quotation: Quotation) -> bytes: ...
