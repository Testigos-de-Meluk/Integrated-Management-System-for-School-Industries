"""Work order (O.T.) aggregate: FR-02-19 … FR-02-23 as corrected in step 5.

Cycle (corrections README, summary item 17):

    PENDING ──export file──▶ REGISTERED_IN_ACCOUNTING ──real dispatch date──▶ RECONCILED
       │                            │                                        │
       └────────────── cancel (reason) ─ from any status but CANCELLED ──────┘

Only a PENDING O.T. can be edited: once exported to Odoo it is read-only. "Registrada en Odoo"
is set only by the export (``mark_registered_in_accounting``), never by hand. O.T.s carry no prices.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from modules.shared_kernel.domain.document_numbers import business_date
from modules.shared_kernel.domain.exceptions import ValidationError

from .exceptions import InvalidWorkOrderItems, InvalidWorkOrderTransition, WorkOrderNotEditable

MAX_QUANTITY = 100_000
MAX_ITEMS = 50
REASON_MAX_LENGTH = 1000
PAST_DATE = "La fecha acordada de entrega no puede estar en el pasado."


class WorkOrderStatus(StrEnum):
    PENDING = "PENDING"  # "Pendiente"
    REGISTERED_IN_ACCOUNTING = "REGISTERED_IN_ACCOUNTING"  # "Registrada en Odoo"
    RECONCILED = "RECONCILED"  # "Conciliada"
    CANCELLED = "CANCELLED"  # "Anulada"


@dataclass(frozen=True, slots=True)
class WorkOrderCustomer:
    """Snapshot of the customer when it was set (the list shows and filters it)."""

    id: UUID
    tax_id: str
    name: str


@dataclass(eq=False, slots=True)
class WorkOrderItem:
    product_id: UUID
    product_code: str  # snapshot: the catalog may change later
    description: str  # snapshot
    unit_of_measure: str  # snapshot
    quantity: int
    id: UUID = field(default_factory=uuid4)


def validate_items(items: list[WorkOrderItem]) -> None:
    if not items:
        raise InvalidWorkOrderItems(
            {"items": ["La orden de trabajo debe tener al menos un producto."]},
            "La orden de trabajo debe tener al menos un producto.",
        )
    if len(items) > MAX_ITEMS:
        raise InvalidWorkOrderItems.for_field("items", f"Máximo {MAX_ITEMS} productos por orden.")
    for item in items:
        if not isinstance(item.quantity, int) or not 0 < item.quantity <= MAX_QUANTITY:
            raise InvalidWorkOrderItems.for_field(
                "items",
                f"Cada cantidad debe ser un número entero entre 1 y {MAX_QUANTITY:,}.".replace(
                    ",", "."
                ),
            )


def _validate_agreed_date(agreed: date | None, today: date) -> date:
    if agreed is None:
        raise ValidationError.for_field(
            "agreed_delivery_date", "Ingrese la fecha acordada de entrega."
        )
    if agreed < today:
        raise ValidationError.for_field("agreed_delivery_date", PAST_DATE)
    return agreed


def clean_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if not text:
        raise ValidationError.for_field("reason", "Indique el motivo de la anulación.")
    if len(text) > REASON_MAX_LENGTH:
        raise ValidationError.for_field("reason", f"Máximo {REASON_MAX_LENGTH} caracteres.")
    return text


@dataclass(eq=False, slots=True)
class WorkOrder:
    number: str  # OT-YYYYMMDD-NNNNN, never changes (US 2.38.3)
    quotation_id: UUID
    quotation_number: str  # snapshot of the source quotation
    customer: WorkOrderCustomer
    items: list[WorkOrderItem]
    agreed_delivery_date: date
    created_at: datetime
    created_by_id: UUID | None
    created_by_name: str
    status: WorkOrderStatus = WorkOrderStatus.PENDING
    actual_dispatch_date: date | None = None
    cancellation_reason: str = ""
    #: Snapshot of the source quotation's approval: the dispatch lead time is measured from it
    #: (FR-02-06). ``None`` only for O.T.s generated before step 5b.
    quotation_approved_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    # --- Factory (FR-02-20) -------------------------------------------------------------------

    @classmethod
    def generate(
        cls,
        *,
        number: str,
        quotation_id: UUID,
        quotation_number: str,
        customer: WorkOrderCustomer,
        items: list[WorkOrderItem],
        agreed_delivery_date: date | None,
        today: date,
        now: datetime,
        by_id: UUID | None,
        by_name: str,
        quotation_approved_at: datetime | None = None,
    ) -> "WorkOrder":
        validate_items(items)
        return cls(
            number=number,
            quotation_id=quotation_id,
            quotation_number=quotation_number,
            quotation_approved_at=quotation_approved_at,
            customer=customer,
            items=items,
            agreed_delivery_date=_validate_agreed_date(agreed_delivery_date, today),
            created_at=now,
            created_by_id=by_id,
            created_by_name=by_name,
        )

    # --- State --------------------------------------------------------------------------------

    @property
    def is_editable(self) -> bool:
        return self.status is WorkOrderStatus.PENDING

    @property
    def is_active(self) -> bool:
        """Counts as "the" O.T. of its quotation (one active O.T. per quotation)."""
        return self.status is not WorkOrderStatus.CANCELLED

    @property
    def was_exported(self) -> bool:
        return self.status in (WorkOrderStatus.REGISTERED_IN_ACCOUNTING, WorkOrderStatus.RECONCILED)

    # --- Use cases ----------------------------------------------------------------------------

    def update(
        self,
        customer: WorkOrderCustomer,
        items: list[WorkOrderItem],
        agreed_delivery_date: date | None,
        today: date,
    ) -> None:
        """FR-02-21 / US 2.38: only while PENDING; the number never changes."""
        if not self.is_editable:
            raise WorkOrderNotEditable()
        validate_items(items)
        if agreed_delivery_date != self.agreed_delivery_date:
            # An unchanged date may already be in the past; a new one cannot.
            self.agreed_delivery_date = _validate_agreed_date(agreed_delivery_date, today)
        self.customer = customer
        self.items = items

    def mark_registered_in_accounting(self) -> None:
        """Called by the export (step 5d), never by a user (FR-02-23 corrected)."""
        if self.status is not WorkOrderStatus.PENDING:
            raise InvalidWorkOrderTransition(
                "Solo una orden de trabajo Pendiente puede quedar Registrada en Odoo."
            )
        self.status = WorkOrderStatus.REGISTERED_IN_ACCOUNTING

    def reconcile(self, actual_dispatch_date: date | None, today: date) -> None:
        """US 2.40: Registrada en Odoo → Conciliada, with the real dispatch date."""
        if self.status is not WorkOrderStatus.REGISTERED_IN_ACCOUNTING:
            raise InvalidWorkOrderTransition(
                "Solo una orden de trabajo Registrada en Odoo puede pasar a Conciliada."
            )
        if actual_dispatch_date is None:
            raise ValidationError.for_field(
                "actual_dispatch_date", "Ingrese la fecha real de despacho."
            )
        if actual_dispatch_date > today:
            raise ValidationError.for_field(
                "actual_dispatch_date", "La fecha real de despacho no puede ser futura."
            )
        if actual_dispatch_date < business_date(self.created_at):
            raise ValidationError.for_field(
                "actual_dispatch_date",
                "La fecha real de despacho no puede ser anterior a la orden de trabajo.",
            )
        self.actual_dispatch_date = actual_dispatch_date
        self.status = WorkOrderStatus.RECONCILED

    def cancel(self, reason: str | None) -> None:
        """US 2.39 corrected: from any status except CANCELLED, always with a reason."""
        if self.status is WorkOrderStatus.CANCELLED:
            raise InvalidWorkOrderTransition("La orden de trabajo ya está anulada.")
        self.cancellation_reason = clean_reason(reason)
        self.status = WorkOrderStatus.CANCELLED

    # --- Audit --------------------------------------------------------------------------------

    def snapshot(self) -> dict[str, object]:
        return {
            "number": self.number,
            "quotation_number": self.quotation_number,
            "status": self.status.value,
            "customer": f"{self.customer.tax_id} · {self.customer.name}",
            "agreed_delivery_date": self.agreed_delivery_date.isoformat(),
            "actual_dispatch_date": (
                self.actual_dispatch_date.isoformat() if self.actual_dispatch_date else None
            ),
            "items": [{"code": i.product_code, "quantity": i.quantity} for i in self.items],
        }
