"""Product aggregate (FR-02-01 … FR-02-04, RN-M2-01).

A product has no price: the catalog is only a repository of products. Products are never deleted;
they are deactivated so historical quotations and work orders keep referencing them.
"""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4

from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.text import REQUIRED, clean_text

from .exceptions import InvalidProductStatusChange

CODE_MAX_LENGTH = 30
NAME_MAX_LENGTH = 200
UNIT_MAX_LENGTH = 30
_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]*$")


class ProductStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


def normalize_code(raw: str) -> str:
    """Codes are case-insensitive: ``sil-001`` and ``SIL-001`` are the same product."""
    return (raw or "").strip().upper()


def _validate_code(code: str, errors: dict[str, list[str]]) -> None:
    if not code:
        errors["code"] = [REQUIRED]
    elif len(code) > CODE_MAX_LENGTH:
        errors["code"] = [f"Máximo {CODE_MAX_LENGTH} caracteres."]
    elif not _CODE_PATTERN.match(code):
        errors["code"] = ["Use solo letras, números y guiones (por ejemplo, SIL-001)."]


@dataclass(eq=False, slots=True)
class Product:
    code: str
    name: str
    unit_of_measure: str
    status: ProductStatus = ProductStatus.ACTIVE
    id: UUID = field(default_factory=uuid4)

    # --- Creation (Factory Method, NFR-05-01) -------------------------------------------------

    @classmethod
    def register(cls, code: str, name: str, unit_of_measure: str) -> "Product":
        """Creates a new product in ``ACTIVE`` status after validating every field."""
        errors: dict[str, list[str]] = {}
        normalized_code = normalize_code(code)
        _validate_code(normalized_code, errors)
        clean_name = clean_text(name, "name", NAME_MAX_LENGTH, errors)
        clean_unit = clean_text(unit_of_measure, "unit_of_measure", UNIT_MAX_LENGTH, errors)
        if errors:
            raise ValidationError(errors)
        return cls(code=normalized_code, name=clean_name, unit_of_measure=clean_unit)

    # --- Behaviour ----------------------------------------------------------------------------

    def update_details(self, name: str, unit_of_measure: str) -> None:
        """Only name and unit can change; the code is immutable (FR-02-03)."""
        errors: dict[str, list[str]] = {}
        clean_name = clean_text(name, "name", NAME_MAX_LENGTH, errors)
        clean_unit = clean_text(unit_of_measure, "unit_of_measure", UNIT_MAX_LENGTH, errors)
        if errors:
            raise ValidationError(errors)
        self.name = clean_name
        self.unit_of_measure = clean_unit

    def activate(self) -> None:
        if self.status is ProductStatus.ACTIVE:
            raise InvalidProductStatusChange("El producto ya se encuentra activo.")
        self.status = ProductStatus.ACTIVE

    def deactivate(self) -> None:
        if self.status is ProductStatus.INACTIVE:
            raise InvalidProductStatusChange("El producto ya se encuentra inactivo.")
        self.status = ProductStatus.INACTIVE

    @property
    def is_selectable(self) -> bool:
        """Only active products can be added to new quotations and work orders (FR-02-04)."""
        return self.status is ProductStatus.ACTIVE

    def snapshot(self) -> dict[str, str]:
        """Plain values for the audit log (old/new values)."""
        return {
            "code": self.code,
            "name": self.name,
            "unit_of_measure": self.unit_of_measure,
            "status": self.status.value,
        }
