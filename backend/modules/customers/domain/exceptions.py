from modules.shared_kernel.domain.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

DUPLICATE_TAX_ID_MESSAGE = "El NIT o número de documento ya se encuentra registrado"


class CustomerNotFound(NotFoundError):
    default_message = "El cliente no existe."


class DuplicateTaxId(ValidationError):
    """FR-02-09: the NIT / document number identifies the customer and must be unique."""

    def __init__(self) -> None:
        super().__init__({"tax_id": [DUPLICATE_TAX_ID_MESSAGE]}, DUPLICATE_TAX_ID_MESSAGE)


class InvalidCustomerStatusChange(ConflictError):
    default_message = "El cambio de estado solicitado no es válido."


class CustomerReadOnly(ConflictError):
    """FR-02-11 / US 2.22.4: an inactive customer's profile is read-only."""

    default_message = "El cliente está inactivo: su ficha es de solo lectura."


class NoteNotFound(NotFoundError):
    default_message = "La nota solicitada no existe."


class NoteEditNotAllowed(PermissionDeniedError):
    """Each note can only be edited by the person who wrote it."""

    default_message = "Solo quien registró la nota puede editarla."
