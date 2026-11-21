"""Link between an account and its authenticator app (FR-01-02, US 1.2).

A user has at most one enrollment. While PENDING, the QR code and secret are valid for 5 minutes;
once CONFIRMED, two-factor authentication is mandatory on every login.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from .exceptions import AlreadyEnrolled, EnrollmentExpired

ENROLLMENT_VALIDITY = timedelta(minutes=5)


class EnrollmentStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"


@dataclass(eq=False, slots=True)
class TotpEnrollment:
    user_id: UUID
    secret: str  # base32; encrypted at rest by the repository
    issued_at: datetime
    expires_at: datetime
    status: EnrollmentStatus = EnrollmentStatus.PENDING
    confirmed_at: datetime | None = None
    last_used_step: int | None = None
    id: UUID = field(default_factory=uuid4)

    @classmethod
    def start(cls, user_id: UUID, secret: str, now: datetime) -> "TotpEnrollment":
        return cls(
            user_id=user_id, secret=secret, issued_at=now, expires_at=now + ENROLLMENT_VALIDITY
        )

    @property
    def is_confirmed(self) -> bool:
        return self.status is EnrollmentStatus.CONFIRMED

    def is_expired(self, now: datetime) -> bool:
        return not self.is_confirmed and now >= self.expires_at

    def restart(self, secret: str, now: datetime) -> None:
        """US 1.2.5: a new QR and secret, with a new 5-minute window."""
        if self.is_confirmed:
            raise AlreadyEnrolled()
        self.secret = secret
        self.issued_at = now
        self.expires_at = now + ENROLLMENT_VALIDITY
        self.status = EnrollmentStatus.PENDING
        self.last_used_step = None

    def ensure_can_be_confirmed(self, now: datetime) -> None:
        if self.is_confirmed:
            raise AlreadyEnrolled()
        if self.is_expired(now):
            self.status = EnrollmentStatus.EXPIRED
            raise EnrollmentExpired()

    def confirm(self, now: datetime, step: int) -> None:
        self.ensure_can_be_confirmed(now)
        self.status = EnrollmentStatus.CONFIRMED
        self.confirmed_at = now
        self.last_used_step = step

    def accept_code_step(self, step: int) -> bool:
        """A code (identified by its 30-second time step) can be used only once."""
        if self.last_used_step is not None and step <= self.last_used_step:
            return False
        self.last_used_step = step
        return True
