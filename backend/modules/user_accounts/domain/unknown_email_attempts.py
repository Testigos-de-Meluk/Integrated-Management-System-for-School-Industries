"""Failed logins with an email that has no account (security audit F-03a).

Real accounts lock after three failures and then answer "Cuenta bloqueada" (FR-01-01, FR-01-14).
If unknown emails kept answering "Correo electrónico o contraseña incorrectos", three attempts
would tell anyone which emails are registered. So unknown emails follow the same counter and
lock, with the same constants as ``User``, and get the same answers at the same moments.
"""

from dataclasses import dataclass
from datetime import datetime

from .user import LOCKOUT_DURATION, MAX_FAILED_LOGIN_ATTEMPTS


@dataclass(slots=True)
class UnknownEmailAttempts:
    failures: int = 0
    locked_until: datetime | None = None

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until

    def register_failure(self, now: datetime) -> bool:
        """Same rule as ``User.register_failed_login``. Returns ``True`` if this one locked it."""
        self.failures += 1
        if self.failures >= MAX_FAILED_LOGIN_ATTEMPTS:
            self.locked_until = now + LOCKOUT_DURATION
            self.failures = 0
            return True
        return False
