from abc import ABC, abstractmethod
from uuid import UUID

from modules.authentication.domain.session import Session
from modules.authentication.domain.totp_enrollment import TotpEnrollment


class SessionRepository(ABC):
    @abstractmethod
    def get(self, session_id: UUID) -> Session | None: ...

    @abstractmethod
    def add(self, session: Session) -> None: ...

    # Each write changes only its own columns and only while the stored row is still ACTIVE, in a
    # single conditional UPDATE. A late write can therefore never bring a closed session back
    # (audit F-01/F-02) nor undo another request's rotation. ``False`` = the row did not match.

    @abstractmethod
    def record_activity(self, session: Session) -> bool:
        """Writes ``last_activity_at`` only. ``False`` if the session is no longer active."""

    @abstractmethod
    def rotate_refresh_token(self, session: Session, expected_refresh_token_id: str) -> bool:
        """Writes the new ``refresh_token_id`` if the session is active and still holds
        ``expected_refresh_token_id``; ``False`` if it was closed or another request rotated."""

    @abstractmethod
    def record_termination(self, session: Session) -> bool:
        """Writes status, reason and time. ``False`` if it was already closed (the first reason
        wins: it is the one the user must be told about)."""

    @abstractmethod
    def active_sessions_of(self, user_id: UUID) -> list[Session]: ...


class EnrollmentRepository(ABC):
    @abstractmethod
    def get_for_user(self, user_id: UUID) -> TotpEnrollment | None: ...

    @abstractmethod
    def save(self, enrollment: TotpEnrollment) -> None:
        """Insert or update. The secret is encrypted at rest by the adapter."""

    @abstractmethod
    def delete_for_user(self, user_id: UUID) -> bool:
        """Removes the user's enrollment. Returns ``True`` if there was one."""
