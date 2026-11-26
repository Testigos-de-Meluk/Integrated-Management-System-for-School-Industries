from abc import ABC, abstractmethod

from modules.user_accounts.domain.unknown_email_attempts import UnknownEmailAttempts


class UnknownEmailAttemptStore(ABC):
    """Short-lived counters of failed logins with unregistered emails (no table, no account).

    ``email`` arrives normalized; adapters must not keep it in clear (it is personal data that
    nobody asked us to store): they key the counter by a keyed hash.
    """

    @abstractmethod
    def get(self, email: str) -> UnknownEmailAttempts: ...

    @abstractmethod
    def save(self, email: str, attempts: UnknownEmailAttempts) -> None: ...
