"""Customer aggregate (FR-02-07 … FR-02-11, RN-M2-08).

``Customer`` is abstract, as in the class diagram (page 6): ``NaturalPerson`` is identified by an ID
document number and shows the person's full name; ``LegalEntity`` is identified by a NIT and shows
its business name. Customers are never deleted: an inactive customer stays visible, read-only.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar
from uuid import UUID, uuid4

from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.text import REQUIRED, clean_text

from .exceptions import CustomerReadOnly, InvalidCustomerStatusChange
from .tax_id import normalize_natural_id, normalize_nit

NAME_MAX_LENGTH = 200
ADDRESS_MAX_LENGTH = 250
PHONE_MAX_LENGTH = 30
EMAIL_MAX_LENGTH = 254
CONTACT_MAX_LENGTH = 150

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[\d\s()-]{7,30}$")


class CustomerType(StrEnum):
    NATURAL_PERSON = "NATURAL_PERSON"
    LEGAL_ENTITY = "LEGAL_ENTITY"


class CustomerStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


def _contact_fields(
    name: str, address: str, primary_phone: str, email: str, commercial_contact: str | None
) -> dict[str, str]:
    """Validates the editable fields and returns them cleaned, or raises ``ValidationError``."""
    errors: dict[str, list[str]] = {}
    values = {
        "name": clean_text(name, "name", NAME_MAX_LENGTH, errors),
        "address": clean_text(address, "address", ADDRESS_MAX_LENGTH, errors),
        "primary_phone": clean_text(primary_phone, "primary_phone", PHONE_MAX_LENGTH, errors),
        "email": (email or "").strip().lower(),
        "commercial_contact": clean_text(
            commercial_contact, "commercial_contact", CONTACT_MAX_LENGTH, errors, required=False
        ),
    }
    if "primary_phone" not in errors and not _PHONE.match(values["primary_phone"]):
        errors["primary_phone"] = ["Ingrese un teléfono válido (solo números, espacios o +)."]
    if not values["email"]:
        errors["email"] = [REQUIRED]
    elif len(values["email"]) > EMAIL_MAX_LENGTH or not _EMAIL.match(values["email"]):
        errors["email"] = [
            "Ingrese un correo electrónico válido (por ejemplo, nombre@empresa.com)."
        ]
    if errors:
        raise ValidationError(errors)
    return values


@dataclass(eq=False)
class Customer(ABC):
    tax_id: str
    name: str
    address: str
    primary_phone: str
    email: str
    commercial_contact: str = ""
    status: CustomerStatus = CustomerStatus.ACTIVE
    id: UUID = field(default_factory=uuid4)

    TYPE: ClassVar[CustomerType]

    # --- Creation (Factory Method, NFR-05-01) -------------------------------------------------

    @staticmethod
    def register(
        customer_type: CustomerType,
        tax_id: str,
        name: str,
        address: str,
        primary_phone: str,
        email: str,
        commercial_contact: str | None = None,
    ) -> "Customer":
        """Creates the right subclass for the customer type, ``ACTIVE`` (FR-02-09)."""
        subclass = NaturalPerson if customer_type is CustomerType.NATURAL_PERSON else LegalEntity
        tax_id_error: dict[str, list[str]] = {}
        normalized, message = subclass.normalize_tax_id(tax_id)
        if normalized is None:
            tax_id_error["tax_id"] = [message]
        try:
            values = _contact_fields(name, address, primary_phone, email, commercial_contact)
        except ValidationError as error:
            raise ValidationError({**tax_id_error, **error.errors}) from None
        if tax_id_error:
            raise ValidationError(tax_id_error)
        return subclass(tax_id=normalized, **values)

    @classmethod
    @abstractmethod
    def normalize_tax_id(cls, raw: str) -> tuple[str | None, str | None]:
        """Returns ``(normalized id, error message)``."""

    # --- Behaviour ----------------------------------------------------------------------------

    @property
    def customer_type(self) -> CustomerType:
        return self.TYPE

    @property
    def is_active(self) -> bool:
        return self.status is CustomerStatus.ACTIVE

    def ensure_editable(self) -> None:
        if not self.is_active:
            raise CustomerReadOnly()

    def update_details(
        self,
        name: str,
        address: str,
        primary_phone: str,
        email: str,
        commercial_contact: str | None,
    ) -> None:
        """Type and NIT/document can never change (FR-02-10); everything else can."""
        self.ensure_editable()
        values = _contact_fields(name, address, primary_phone, email, commercial_contact)
        for key, value in values.items():
            setattr(self, key, value)

    def deactivate(self) -> None:
        if not self.is_active:
            raise InvalidCustomerStatusChange("El cliente ya se encuentra inactivo.")
        self.status = CustomerStatus.INACTIVE

    def activate(self) -> None:
        if self.is_active:
            raise InvalidCustomerStatusChange("El cliente ya se encuentra activo.")
        self.status = CustomerStatus.ACTIVE

    def snapshot(self) -> dict[str, str]:
        return {
            "customer_type": self.customer_type.value,
            "tax_id": self.tax_id,
            "name": self.name,
            "address": self.address,
            "primary_phone": self.primary_phone,
            "email": self.email,
            "commercial_contact": self.commercial_contact,
            "status": self.status.value,
        }


@dataclass(eq=False)
class NaturalPerson(Customer):
    """Individual customer: ``name`` is the full name, ``tax_id`` the ID document number."""

    TYPE: ClassVar[CustomerType] = CustomerType.NATURAL_PERSON

    @classmethod
    def normalize_tax_id(cls, raw: str) -> tuple[str | None, str | None]:
        digits = normalize_natural_id(raw)
        if digits is None:
            return None, "Ingrese el número de documento: de 5 a 15 dígitos."
        return digits, None


@dataclass(eq=False)
class LegalEntity(Customer):
    """Company customer: ``name`` is the business name, ``tax_id`` the NIT with check digit."""

    TYPE: ClassVar[CustomerType] = CustomerType.LEGAL_ENTITY

    @classmethod
    def normalize_tax_id(cls, raw: str) -> tuple[str | None, str | None]:
        return normalize_nit(raw)


def customer_class(customer_type: CustomerType) -> type[Customer]:
    return NaturalPerson if customer_type is CustomerType.NATURAL_PERSON else LegalEntity
