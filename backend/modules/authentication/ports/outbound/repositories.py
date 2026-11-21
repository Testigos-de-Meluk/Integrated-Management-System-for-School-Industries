from abc import ABC, abstractmethod
from uuid import UUID

from modules.authentication.domain.session import Session
from modules.authentication.domain.totp_enrollment import TotpEnrollment


class SessionRepository(ABC):
    @abstractmethod
    def get(self, session_id: UUID) -> Session | None: ...

    @abstractmethod
    def add(self, session: Session) -> None: ...

    @abstractmethod
    def update(self, session: Session) -> None: ...

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
