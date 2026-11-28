"""Export batch (EXPORT_BATCH; FR-02-18, US 2.34, step 5d).

One batch = one generated file with the selected work orders, imported into **Odoo Community 20**
by hand (team decision with Industrias Escolares, November 2026: Odoo replaces Siigo Pyme). The
file is kept so it can be downloaded again from "Lotes exportados"; importing it twice in Odoo
duplicates the sale orders, so the screen warns before a second download.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from modules.shared_kernel.domain.document_numbers import BUSINESS_TIMEZONE
from modules.shared_kernel.domain.exceptions import ValidationError

MAX_WORK_ORDERS = 200
FILE_PREFIX = "IMSI-Odoo"


def batch_file_name(created_at: datetime, extension: str) -> str:
    """``IMSI-Odoo-YYYYMMDD-HHMMSS.<ext>`` in Colombian time."""
    local = created_at.astimezone(BUSINESS_TIMEZONE)
    return f"{FILE_PREFIX}-{local:%Y%m%d-%H%M%S}.{extension}"


def validate_selection(work_order_ids: frozenset[UUID]) -> None:
    if not work_order_ids:
        raise ValidationError.for_field(
            "work_order_ids", "Seleccione al menos una orden de trabajo para exportar."
        )
    if len(work_order_ids) > MAX_WORK_ORDERS:
        raise ValidationError.for_field(
            "work_order_ids", f"Máximo {MAX_WORK_ORDERS} órdenes de trabajo por archivo."
        )


@dataclass(eq=False, slots=True)
class ExportBatch:
    file_name: str
    created_at: datetime
    created_by_id: UUID | None
    created_by_name: str
    work_order_numbers: tuple[str, ...]
    id: UUID = field(default_factory=uuid4)

    @classmethod
    def generate(
        cls,
        *,
        work_order_numbers: tuple[str, ...],
        extension: str,
        now: datetime,
        by_id: UUID | None,
        by_name: str,
    ) -> "ExportBatch":
        if not work_order_numbers:
            raise ValidationError.for_field(
                "work_order_ids", "Seleccione al menos una orden de trabajo para exportar."
            )
        return cls(
            file_name=batch_file_name(now, extension),
            created_at=now,
            created_by_id=by_id,
            created_by_name=by_name,
            work_order_numbers=work_order_numbers,
        )
