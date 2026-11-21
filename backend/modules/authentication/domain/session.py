"""Login session (FR-01-05 single session, FR-01-06 inactivity).

JWTs are stateless: a token stays valid until it expires. The session is the server-side record
that lets the system close access before that: every token carries the session id and every
request checks that the session is still active.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

#: FR-01-06: 15 continuous minutes without activity close the session.
INACTIVITY_TIMEOUT = timedelta(minutes=15)
#: Activity is written at most every 30 seconds, to avoid one database write per request.
ACTIVITY_WRITE_INTERVAL = timedelta(seconds=30)


class SessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    TERMINATED = "TERMINATED"


class TerminationReason(StrEnum):
    LOGOUT = "LOGOUT"
    INACTIVITY = "INACTIVITY"
    NEW_LOGIN = "NEW_LOGIN"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    TOKEN_REUSE = "TOKEN_REUSE"  # an old refresh token was presented again (possible theft)


@dataclass(eq=False, slots=True)
class Session:
    user_id: UUID
    created_at: datetime
    last_activity_at: datetime
    refresh_token_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    termination_reason: TerminationReason | None = None
    terminated_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    @classmethod
    def open(cls, user_id: UUID, now: datetime, refresh_token_id: str) -> "Session":
        return cls(
            user_id=user_id, created_at=now, last_activity_at=now, refresh_token_id=refresh_token_id
        )

    @property
    def is_terminated(self) -> bool:
        return self.status is SessionStatus.TERMINATED

    def is_inactive(self, now: datetime) -> bool:
        return now - self.last_activity_at >= INACTIVITY_TIMEOUT

    def touch(self, now: datetime) -> bool:
        """Records user activity. Returns ``True`` when it changed (and must be saved)."""
        if now - self.last_activity_at >= ACTIVITY_WRITE_INTERVAL:
            self.last_activity_at = now
            return True
        return False

    def rotate_refresh_token(self, new_token_id: str) -> None:
        """Each refresh issues a new refresh token; the previous one stops working."""
        self.refresh_token_id = new_token_id

    def terminate(self, reason: TerminationReason, now: datetime) -> None:
        if self.is_terminated:
            return  # keep the first reason: it is the one the user must be told about
        self.status = SessionStatus.TERMINATED
        self.termination_reason = reason
        self.terminated_at = now
