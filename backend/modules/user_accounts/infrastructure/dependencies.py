"""Composition root of the User Accounts module."""

from functools import lru_cache

from django.conf import settings

from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger
from modules.shared_kernel.infrastructure.events.in_process_event_bus import event_bus
from modules.shared_kernel.infrastructure.notifications.celery_email_notifier import (
    CeleryEmailNotifier,
)
from modules.shared_kernel.infrastructure.security.bcrypt_password_hasher import (
    BcryptPasswordHasher,
)
from modules.user_accounts.application.account_access_service import AccountAccessService
from modules.user_accounts.application.user_account_service import UserAccountService
from modules.user_accounts.ports.inbound.account_access import AccountAccess
from modules.user_accounts.ports.inbound.user_account_use_cases import UserAccountUseCases

from .persistence.cache_unknown_email_attempts import CacheUnknownEmailAttemptStore
from .persistence.django_user_repository import DjangoUserRepository


@lru_cache(maxsize=1)
def password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher(rounds=settings.BCRYPT_ROUNDS)


@lru_cache(maxsize=1)
def account_access() -> AccountAccess:
    """Port offered to other modules (the authentication module) for login checks."""
    return AccountAccessService(
        DjangoUserRepository(), password_hasher(), CacheUnknownEmailAttemptStore()
    )


@lru_cache(maxsize=1)
def user_account_use_cases() -> UserAccountUseCases:
    return UserAccountService(
        repository=DjangoUserRepository(),
        password_hasher=password_hasher(),
        notifier=CeleryEmailNotifier(),
        audit_logger=DatabaseAuditLogger(),
        events=event_bus,
        login_url=f"{settings.FRONTEND_URL.rstrip('/')}/login",
    )
