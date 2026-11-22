"""Quotation aggregate (FR-02-05, FR-02-12 … FR-02-15, RN-M2-01 … RN-M2-04).

A preliminary quotation is produced by the public virtual assistant with *estimated price ranges*,
never fixed prices. Products without price history are shown as "Precio por confirmar" and the
Administrador sets their price when reviewing (sub-step 4b).
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.money import PriceRange

from .exceptions import InvalidQuotationItems

MAX_QUANTITY = 100_000
MAX_ITEMS = 50
DEFAULT_VALIDITY_DAYS = 15  # mockup: "Vigencia 15 días"

REQUIRED = "Este campo es obligatorio."
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[\d\s()-]{7,30}$")
_TAX_ID = re.compile(r"^[\d.\s-]{5,20}$")


class QuotationStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"  # "Pendiente de revisión"
    MODIFIED = "MODIFIED"  # "Modificada"
    APPROVED = "APPROVED"  # "Aprobada"
    REJECTED = "REJECTED"  # "Rechazada"


class DispatchDateSource(StrEnum):
    SUGGESTED = "SUGGESTED"
    MANUAL = "MANUAL"


@dataclass(frozen=True, slots=True)
class RequesterContact:
    """Who asked for the quotation (FR-02-05). Institution and NIT are optional."""

    full_name: str
    email: str
    phone: str
    institution: str = ""
    tax_id: str = ""

    @classmethod
    def create(
        cls,
        full_name: str,
        email: str,
        phone: str,
        institution: str | None = None,
        tax_id: str | None = None,
    ) -> "RequesterContact":
        errors: dict[str, list[str]] = {}
        name = " ".join((full_name or "").split())
        clean_email = (email or "").strip().lower()
        clean_phone = " ".join((phone or "").split())
        clean_institution = " ".join((institution or "").split())
        clean_tax_id = (tax_id or "").strip()

        if not name:
            errors["full_name"] = [REQUIRED]
        elif len(name) > 150:
            errors["full_name"] = ["Máximo 150 caracteres."]
        if not clean_email:
            errors["email"] = [REQUIRED]
        elif len(clean_email) > 254 or not _EMAIL.match(clean_email):
            errors["email"] = [
                "Ingrese un correo electrónico válido (por ejemplo, nombre@colegio.edu.co)."
            ]
        if not clean_phone:
            errors["phone"] = [REQUIRED]
        elif not _PHONE.match(clean_phone):
            errors["phone"] = ["Ingrese un teléfono válido (solo números, espacios o +)."]
        if len(clean_institution) > 200:
            errors["institution"] = ["Máximo 200 caracteres."]
        if clean_tax_id and not _TAX_ID.match(clean_tax_id):
            errors["tax_id"] = ["Use solo números, puntos y guion (por ejemplo, 900456789-1)."]
        if errors:
            raise ValidationError(errors)
        return cls(name, clean_email, clean_phone, clean_institution, clean_tax_id)


@dataclass(eq=False, slots=True)
class QuotationItem:
    product_id: UUID
    product_code: str  # snapshot: the catalog may change later
    description: str  # snapshot
    unit_of_measure: str  # snapshot
    quantity: int
    unit_price_range: PriceRange | None  # None = "Precio por confirmar"
    final_unit_price: Decimal | None = None  # set by the Administrador on approval (4b)
    id: UUID = field(default_factory=uuid4)

    @property
    def subtotal_range(self) -> PriceRange | None:
        return self.unit_price_range.times(self.quantity) if self.unit_price_range else None


def validate_quantity(quantity: int) -> None:
    if not isinstance(quantity, int) or quantity <= 0 or quantity > MAX_QUANTITY:
        raise InvalidQuotationItems(
            f"Cada cantidad debe ser un número entero entre 1 y {MAX_QUANTITY:,}.".replace(",", ".")
        )


@dataclass(eq=False, slots=True)
class Quotation:
    number: str  # human reference, e.g. COT-2026-0001
    issued_at: datetime
    requester: RequesterContact
    items: list[QuotationItem]
    valid_until: date
    status: QuotationStatus = QuotationStatus.PENDING_REVIEW
    customer_id: UUID | None = None  # linked to a registered customer later (4b / step 5)
    estimated_dispatch_date: date | None = None
    dispatch_date_source: DispatchDateSource | None = None
    commercial_terms: str = ""
    rejection_reason: str = ""
    access_key: str = ""  # lets the requester download / email *this* quotation only
    id: UUID = field(default_factory=uuid4)

    # --- Creation (Factory Method, NFR-05-01) -------------------------------------------------

    @classmethod
    def request(
        cls,
        number: str,
        requester: RequesterContact,
        items: list[QuotationItem],
        now: datetime,
        access_key: str,
        suggested_dispatch_date: date | None = None,
        validity_days: int = DEFAULT_VALIDITY_DAYS,
    ) -> "Quotation":
        """A preliminary quotation from the virtual assistant, "Pendiente de revisión"."""
        if not items:
            raise InvalidQuotationItems("Agregue al menos un producto a la solicitud.")
        if len(items) > MAX_ITEMS:
            raise InvalidQuotationItems(f"Máximo {MAX_ITEMS} productos por solicitud.")
        for item in items:
            validate_quantity(item.quantity)
        return cls(
            number=number,
            issued_at=now,
            requester=requester,
            items=items,
            valid_until=(now + timedelta(days=validity_days)).date(),
            estimated_dispatch_date=suggested_dispatch_date,
            dispatch_date_source=DispatchDateSource.SUGGESTED if suggested_dispatch_date else None,
            access_key=access_key,
        )

    # --- Totals ---------------------------------------------------------------------------------

    @property
    def estimated_total(self) -> PriceRange | None:
        """Sum of the priced lines; ``None`` when no line has an estimate."""
        ranges = [item.subtotal_range for item in self.items if item.subtotal_range]
        if not ranges:
            return None
        total = ranges[0]
        for subtotal in ranges[1:]:
            total = total + subtotal
        return total

    @property
    def unpriced_items(self) -> int:
        return sum(1 for item in self.items if item.unit_price_range is None)

    def snapshot(self) -> dict:
        total = self.estimated_total
        return {
            "number": self.number,
            "status": self.status.value,
            "requester_email": self.requester.email,
            "items": [{"product_code": i.product_code, "quantity": i.quantity} for i in self.items],
            "estimated_total_min": str(total.min) if total else None,
            "estimated_total_max": str(total.max) if total else None,
            "unpriced_items": self.unpriced_items,
        }
