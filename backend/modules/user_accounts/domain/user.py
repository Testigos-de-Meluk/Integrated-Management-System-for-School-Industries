"""User aggregate (FR-01-10 … FR-01-14, RN-M1-01).

Accounts are individual, always have exactly one of the three fixed roles, are never deleted
(only deactivated) and keep their email forever. The temporary lockout lives here because it is a
rule about the account itself, whoever asks for it.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.security import RoleType

from .exceptions import InvalidAccountStatusChange

FULL_NAME_MAX_LENGTH = 150
EMAIL_MAX_LENGTH = 254
JOB_TITLE_MAX_LENGTH = 100

#: FR-01-14 / RN-M1-02: 3 consecutive failures lock the account for 15 minutes.
MAX_FAILED_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION = timedelta(minutes=15)

REQUIRED = "Este campo es obligatorio."
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


def normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _clean_text(value: str, field_name: str, max_length: int, errors: dict) -> str:
    cleaned = " ".join((value or "").split())
    if not cleaned:
        errors[field_name] = [REQUIRED]
    elif len(cleaned) > max_length:
        errors[field_name] = [f"Máximo {max_length} caracteres."]
    return cleaned


def _validate_email(email: str, errors: dict) -> None:
    if not email:
        errors["email"] = [REQUIRED]
    elif len(email) > EMAIL_MAX_LENGTH or not _EMAIL_PATTERN.match(email):
        errors["email"] = [
            "Ingrese un correo electrónico válido (por ejemplo, nombre@empresa.com)."
        ]


@dataclass(eq=False, slots=True)
class User:
    full_name: str
    email: str
    job_title: str
    role: RoleType
    password_hash: str
    status: AccountStatus = AccountStatus.ACTIVE
    last_access_at: datetime | None = None
    failed_login_attempts: int = 0
    last_failed_login_at: datetime | None = None
    locked_until: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    # --- Creation (Factory Method, NFR-05-01) -------------------------------------------------

    @classmethod
    def register(
        cls, full_name: str, email: str, job_title: str, role: RoleType, password_hash: str
    ) -> "User":
        """Creates an ``ACTIVE`` account (FR-01-11). The password arrives already hashed."""
        errors: dict[str, list[str]] = {}
        clean_name = _clean_text(full_name, "full_name", FULL_NAME_MAX_LENGTH, errors)
        clean_email = normalize_email(email)
        _validate_email(clean_email, errors)
        clean_job = _clean_text(job_title, "job_title", JOB_TITLE_MAX_LENGTH, errors)
        if errors:
            raise ValidationError(errors)
        return cls(
            full_name=clean_name,
            email=clean_email,
            job_title=clean_job,
            role=role,
            password_hash=password_hash,
        )

    # --- Profile and permissions (FR-01-12) ---------------------------------------------------

    def update_profile(self, full_name: str, job_title: str) -> None:
        """The email is the login key and can never change, so there is no method for it."""
        errors: dict[str, list[str]] = {}
        clean_name = _clean_text(full_name, "full_name", FULL_NAME_MAX_LENGTH, errors)
        clean_job = _clean_text(job_title, "job_title", JOB_TITLE_MAX_LENGTH, errors)
        if errors:
            raise ValidationError(errors)
        self.full_name = clean_name
        self.job_title = clean_job

    def change_role(self, role: RoleType) -> None:
        self.role = role

    def change_password_hash(self, password_hash: str) -> None:
        self.password_hash = password_hash

    # --- Status (FR-01-13) --------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.status is AccountStatus.ACTIVE

    def deactivate(self) -> None:
        if not self.is_active:
            raise InvalidAccountStatusChange("La cuenta ya se encuentra inactiva.")
        self.status = AccountStatus.INACTIVE

    def activate(self) -> None:
        if self.is_active:
            raise InvalidAccountStatusChange("La cuenta ya se encuentra activa.")
        self.status = AccountStatus.ACTIVE

    # --- Temporary lockout (FR-01-14) ---------------------------------------------------------

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until

    def register_failed_login(self, now: datetime) -> bool:
        """Counts a failed password or TOTP code. Returns ``True`` if this attempt locked it."""
        self.failed_login_attempts += 1
        self.last_failed_login_at = now
        if self.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            self.locked_until = now + LOCKOUT_DURATION
            self.failed_login_attempts = 0  # a fresh count starts when the lock expires
            return True
        return False

    def register_successful_login(self, now: datetime) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_access_at = now

    def unlock(self) -> None:
        """Manual unlock by an administrator (US 1.23)."""
        self.failed_login_attempts = 0
        self.locked_until = None

    # --- Audit --------------------------------------------------------------------------------

    def snapshot(self) -> dict[str, str]:
        """Values for the audit log. The password hash is never included (NFR-01-02)."""
        return {
            "full_name": self.full_name,
            "email": self.email,
            "job_title": self.job_title,
            "role": self.role.value,
            "status": self.status.value,
        }
