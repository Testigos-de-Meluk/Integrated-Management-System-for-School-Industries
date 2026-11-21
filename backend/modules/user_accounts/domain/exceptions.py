from modules.shared_kernel.domain.exceptions import ConflictError, NotFoundError, ValidationError

DUPLICATE_EMAIL_MESSAGE = "El correo electrónico ya se encuentra registrado en el sistema"


class UserNotFound(NotFoundError):
    default_message = "La cuenta de usuario solicitada no existe."


class DuplicateEmail(ValidationError):
    """FR-01-11: the email identifies the account and must be unique."""

    def __init__(self) -> None:
        super().__init__({"email": [DUPLICATE_EMAIL_MESSAGE]}, DUPLICATE_EMAIL_MESSAGE)


class InvalidAccountStatusChange(ConflictError):
    default_message = "El cambio de estado solicitado no es válido."


class SelfManagementNotAllowed(ConflictError):
    """Prevents an administrator from locking themselves (or the company) out of the system."""

    default_message = "No puede desactivar su propia cuenta ni cambiar su propio rol."
