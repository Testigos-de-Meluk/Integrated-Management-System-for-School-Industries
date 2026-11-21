"""Authentication errors. Messages are the ones defined in the requirements (in Spanish); ``code``
lets the frontend decide what to do (e.g. go back to the login screen with the right notice)."""

from datetime import datetime
from math import ceil

from modules.shared_kernel.domain.exceptions import AuthenticationError, ConflictError


class InvalidCredentials(AuthenticationError):
    default_message = "Correo electrónico o contraseña incorrectos"
    code = "INVALID_CREDENTIALS"


class AccountInactive(AuthenticationError):
    default_message = "Su cuenta se encuentra desactivada. Contacte al administrador"
    code = "ACCOUNT_INACTIVE"


class AccountLocked(AuthenticationError):
    code = "ACCOUNT_LOCKED"

    def __init__(self, locked_until: datetime | None, now: datetime) -> None:
        minutes = 15
        if locked_until is not None:
            minutes = max(1, ceil((locked_until - now).total_seconds() / 60))
        super().__init__(
            "Cuenta bloqueada temporalmente por intentos fallidos. "
            f"Intente de nuevo en {minutes} minuto{'s' if minutes != 1 else ''}."
        )


class InvalidVerificationCode(AuthenticationError):
    default_message = "Código de verificación incorrecto o expirado"
    code = "INVALID_CODE"


class PreAuthExpired(AuthenticationError):
    default_message = "La verificación expiró. Inicie sesión de nuevo."
    code = "PRE_AUTH_EXPIRED"


class EnrollmentExpired(ConflictError):
    default_message = "El tiempo de vinculación ha expirado. Por favor, genere un nuevo código"
    code = "ENROLLMENT_EXPIRED"


class EnrollmentNotStarted(ConflictError):
    default_message = "Primero genere el código QR de vinculación."
    code = "ENROLLMENT_NOT_STARTED"


class AlreadyEnrolled(ConflictError):
    default_message = "Ya existe una aplicación autenticadora vinculada a esta cuenta."
    code = "ALREADY_ENROLLED"


class SessionReplaced(AuthenticationError):
    default_message = (
        "Su sesión ha sido cerrada debido a un nuevo inicio de sesión en otro dispositivo"
    )
    code = "SESSION_REPLACED"


class SessionExpired(AuthenticationError):
    default_message = "Su sesión ha caducado por inactividad"
    code = "SESSION_EXPIRED"


class SessionEnded(AuthenticationError):
    default_message = "Su sesión ha finalizado. Inicie sesión de nuevo."
    code = "SESSION_ENDED"
