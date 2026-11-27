"""Quotation aggregate (FR-02-05, FR-02-12 … FR-02-15, RN-M2-01 … RN-M2-04).

A preliminary quotation is produced by the public virtual assistant with *estimated price ranges*,
never fixed prices. Products without price history are shown as "Precio por confirmar" and the
Administrador sets their price when reviewing.

Review (US 2.25 … US 2.29): while "Pendiente de revisión" or "Modificada" the Administrador can
modify it (→ "Modificada"), approve it with a final unit price per item and a dispatch date
(→ "Aprobada") or reject it with a reason (→ "Rechazada"). Approved and rejected quotations are
immutable; the only later change allowed is linking a customer to an approved quotation that has
none, because a work order requires one (US 2.37, criterion 2).
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from modules.shared_kernel.domain.document_numbers import business_date
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.money import PriceRange, to_pesos
from modules.shared_kernel.domain.text import REQUIRED

from .exceptions import ApprovalIncomplete, InvalidQuotationItems, QuotationLocked
from .pricing import PriceSource

MAX_QUANTITY = 100_000
MAX_ITEMS = 50
DEFAULT_VALIDITY_DAYS = 15  # mockup: "Vigencia 15 días"
MAX_UNIT_PRICE = Decimal(1_000_000_000)  # per unit; totals are stored as DECIMAL(18, 0)
TERMS_MAX_LENGTH = 2000
REASON_MAX_LENGTH = 1000

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
    price_source: PriceSource | None = None  # where the estimated range came from
    id: UUID = field(default_factory=uuid4)

    @property
    def subtotal_range(self) -> PriceRange | None:
        return self.unit_price_range.times(self.quantity) if self.unit_price_range else None

    @property
    def final_subtotal(self) -> Decimal | None:
        return self.final_unit_price * self.quantity if self.final_unit_price is not None else None


def validate_final_price(value: Decimal | None) -> Decimal | None:
    """Whole Colombian pesos, greater than zero. ``None`` = not set yet."""
    if value is None:
        return None
    price = to_pesos(value)
    if price <= 0 or price > MAX_UNIT_PRICE:
        raise InvalidQuotationItems("Cada precio unitario final debe ser un valor mayor que cero.")
    return price


def clean_multiline_text(value: str | None, field_name: str, max_length: int) -> str:
    """Free text such as commercial terms or a reason: unlike ``shared_kernel.domain.text.
    clean_text`` (names), it keeps line breaks and inner spacing, and raises at once."""
    text = (value or "").strip()
    if len(text) > max_length:
        raise ValidationError.for_field(field_name, f"Máximo {max_length} caracteres.")
    return text


def validate_quantity(quantity: int) -> None:
    if not isinstance(quantity, int) or quantity <= 0 or quantity > MAX_QUANTITY:
        raise InvalidQuotationItems(
            f"Cada cantidad debe ser un número entero entre 1 y {MAX_QUANTITY:,}.".replace(",", ".")
        )


@dataclass(eq=False, slots=True)
class Quotation:
    number: str  # human reference, e.g. COT-20261127-00042
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
    approved_at: datetime | None = None
    approved_by_id: UUID | None = None
    approved_by_name: str = ""  # snapshot, like the author of a commercial note
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

    @property
    def final_total(self) -> Decimal | None:
        """Sum of the final prices; ``None`` until every item has one."""
        subtotals = [item.final_subtotal for item in self.items]
        if not subtotals or any(s is None for s in subtotals):
            return None
        return sum(subtotals, Decimal(0))

    # --- Review (US 2.27 … US 2.29) -------------------------------------------------------------

    @property
    def is_editable(self) -> bool:
        return self.status in (QuotationStatus.PENDING_REVIEW, QuotationStatus.MODIFIED)

    def ensure_editable(self) -> None:
        if not self.is_editable:
            raise QuotationLocked()

    def modify(
        self,
        items: list[QuotationItem],
        commercial_terms: str | None,
        dispatch_date: date | None,
        today: date,
        suggested_dispatch_date: date | None = None,
    ) -> None:
        """Quantities, products, final unit prices, terms and dispatch date (US 2.28, US 2.13)."""
        self.ensure_editable()
        if not items:
            raise InvalidQuotationItems("La cotización debe tener al menos un producto.")
        if len(items) > MAX_ITEMS:
            raise InvalidQuotationItems(f"Máximo {MAX_ITEMS} productos por cotización.")
        for item in items:
            validate_quantity(item.quantity)
            item.final_unit_price = validate_final_price(item.final_unit_price)
        terms = clean_multiline_text(commercial_terms, "commercial_terms", TERMS_MAX_LENGTH)
        self._set_dispatch_date(dispatch_date, today, suggested_dispatch_date)
        self.items = items
        self.commercial_terms = terms
        self.status = QuotationStatus.MODIFIED

    def approve(
        self,
        final_prices: dict[UUID, Decimal],
        dispatch_date: date | None,
        commercial_terms: str | None,
        approved_by_id: UUID | None,
        approved_by_name: str,
        now: datetime,
        validity_days: int = DEFAULT_VALIDITY_DAYS,
        suggested_dispatch_date: date | None = None,
    ) -> None:
        """Formalizes the quotation with final prices (FR-02-13, US 2.27). Immutable afterwards.

        The validity period of the formal quotation starts on the approval date.
        """
        self.ensure_editable()
        if set(final_prices) - {item.id for item in self.items}:
            raise InvalidQuotationItems("Uno o más productos no pertenecen a esta cotización.")
        prices = {item_id: validate_final_price(price) for item_id, price in final_prices.items()}
        terms = clean_multiline_text(commercial_terms, "commercial_terms", TERMS_MAX_LENGTH)

        errors: dict[str, list[str]] = {}
        if any(prices.get(i.id, i.final_unit_price) is None for i in self.items):
            errors["items"] = ["Defina el precio unitario final de todos los productos."]
        if dispatch_date is None:
            errors["dispatch_date"] = ["Ingrese la fecha de despacho antes de aprobar."]
        if errors:
            messages = [message for field_errors in errors.values() for message in field_errors]
            raise ApprovalIncomplete(errors, " ".join(messages))
        self._set_dispatch_date(dispatch_date, business_date(now), suggested_dispatch_date)

        for item in self.items:
            if prices.get(item.id) is not None:
                item.final_unit_price = prices[item.id]
        self.commercial_terms = terms
        self.status = QuotationStatus.APPROVED
        self.approved_at = now
        self.approved_by_id = approved_by_id
        self.approved_by_name = approved_by_name
        self.valid_until = (now + timedelta(days=validity_days)).date()

    def reject(self, reason: str | None) -> None:
        """Final state (FR-02-15, RN-M2-04): it never returns to a preliminary status."""
        self.ensure_editable()
        text = clean_multiline_text(reason, "reason", REASON_MAX_LENGTH)
        if not text:
            raise ValidationError.for_field("reason", "Indique el motivo del rechazo.")
        self.status = QuotationStatus.REJECTED
        self.rejection_reason = text

    def link_customer(self, customer_id: UUID | None) -> None:
        """While in review it can change freely; once approved, it can only be set if empty."""
        if self.is_editable:
            self.customer_id = customer_id
            return
        if self.status is QuotationStatus.APPROVED and self.customer_id is None and customer_id:
            self.customer_id = customer_id
            return
        raise QuotationLocked()

    def _set_dispatch_date(
        self, dispatch_date: date | None, today: date, suggested: date | None = None
    ) -> None:
        """``suggested`` is the median recalculated during the review (FR-02-06): accepting it
        keeps the source SUGGESTED; any other date is MANUAL."""
        if dispatch_date == self.estimated_dispatch_date:
            return  # unchanged: keeps its source (a confirmed suggestion stays SUGGESTED)
        if dispatch_date is not None and dispatch_date < today:
            raise ValidationError.for_field(
                "dispatch_date", "La fecha de despacho no puede ser anterior a hoy."
            )
        self.estimated_dispatch_date = dispatch_date
        if dispatch_date is None:
            self.dispatch_date_source = None
        elif dispatch_date == suggested:
            self.dispatch_date_source = DispatchDateSource.SUGGESTED
        else:
            self.dispatch_date_source = DispatchDateSource.MANUAL

    def snapshot(self) -> dict:
        """What the audit log keeps: the estimated range and the final price of every item are
        recorded side by side (RN-M2-02)."""
        total = self.estimated_total
        final_total = self.final_total
        return {
            "number": self.number,
            "status": self.status.value,
            "requester_email": self.requester.email,
            "customer_id": str(self.customer_id) if self.customer_id else None,
            "items": [_item_snapshot(i) for i in self.items],
            "estimated_total_min": str(total.min) if total else None,
            "estimated_total_max": str(total.max) if total else None,
            "final_total": str(final_total) if final_total is not None else None,
            "unpriced_items": self.unpriced_items,
            "estimated_dispatch_date": (
                self.estimated_dispatch_date.isoformat() if self.estimated_dispatch_date else None
            ),
            "commercial_terms": self.commercial_terms,
        }


def _item_snapshot(item: QuotationItem) -> dict:
    estimated = item.unit_price_range
    return {
        "product_code": item.product_code,
        "quantity": item.quantity,
        "estimated_unit_min": str(estimated.min) if estimated else None,
        "estimated_unit_max": str(estimated.max) if estimated else None,
        "estimate_source": item.price_source.value if item.price_source else None,
        "final_unit_price": str(item.final_unit_price)
        if item.final_unit_price is not None
        else None,
    }
