from abc import ABC, abstractmethod
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.user_accounts.domain.user import User
from modules.user_accounts.ports.inbound.user_account_use_cases import UserFilters


class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def exists_with_email(self, email: str) -> bool: ...

    @abstractmethod
    def add(self, user: User) -> None:
        """Stores a new account. Raises ``DuplicateEmail`` if the email already exists."""

    @abstractmethod
    def update(self, user: User) -> None: ...

    @abstractmethod
    def search(self, filters: UserFilters, page_request: PageRequest) -> Page[User]:
        """One page of accounts matching every filter, ordered by full name."""
