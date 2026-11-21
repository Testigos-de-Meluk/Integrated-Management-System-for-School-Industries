from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.user_accounts.domain.exceptions import DuplicateEmail
from modules.user_accounts.domain.user import User
from modules.user_accounts.ports.inbound.user_account_use_cases import UserFilters
from modules.user_accounts.ports.outbound.user_repository import UserRepository


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    def exists_with_email(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def add(self, user: User) -> None:
        if self.exists_with_email(user.email):
            raise DuplicateEmail()
        self.users[user.id] = user

    def update(self, user: User) -> None:
        self.users[user.id] = user

    def search(self, filters: UserFilters, page_request: PageRequest) -> Page[User]:
        items = sorted(self.users.values(), key=lambda u: u.full_name)
        if filters.name:
            items = [u for u in items if filters.name.lower() in u.full_name.lower()]
        if filters.role:
            items = [u for u in items if u.role.value == filters.role]
        if filters.status:
            items = [u for u in items if u.status.value == filters.status]
        start = page_request.offset
        return Page(items[start : start + page_request.size], len(items), page_request)
