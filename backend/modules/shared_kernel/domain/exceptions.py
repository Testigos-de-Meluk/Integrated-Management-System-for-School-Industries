"""Base domain errors shared by every module.

Messages are user-facing, so they are written in Spanish (see the language convention in
``Workshops/Corrections/README.md``). The REST layer translates each error type to an HTTP status.
"""


class DomainError(Exception):
    """Base class for every business-rule violation."""

    default_message = "No fue posible completar la operación."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class ValidationError(DomainError):
    """Input data breaks a business rule. ``errors`` maps field names to messages."""

    default_message = "Los datos enviados no son válidos. Revise los campos marcados."

    def __init__(
        self, errors: dict[str, list[str]] | None = None, message: str | None = None
    ) -> None:
        super().__init__(message)
        self.errors = errors or {}

    @classmethod
    def for_field(cls, field: str, message: str) -> "ValidationError":
        return cls({field: [message]}, message)


class NotFoundError(DomainError):
    default_message = "El recurso solicitado no existe."


class ConflictError(DomainError):
    """The operation is not allowed in the current state of the entity."""

    default_message = "La operación no es posible en el estado actual."


class PermissionDeniedError(DomainError):
    default_message = "No tiene permisos para realizar esta acción."
