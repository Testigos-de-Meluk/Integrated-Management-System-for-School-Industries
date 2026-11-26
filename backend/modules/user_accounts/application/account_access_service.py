"""Implements the ``AccountAccess`` port used by the authentication module."""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.shared_kernel.ports.outbound.password_hasher import PasswordHasher
from modules.user_accounts.domain.user import User, normalize_email
from modules.user_accounts.ports.inbound.account_access import (
    AccountAccess,
    AccountSummary,
    CredentialCheckOutcome,
    CredentialCheckResult,
    FailedAttemptResult,
)
from modules.user_accounts.ports.outbound.unknown_email_attempt_store import (
    UnknownEmailAttemptStore,
)
from modules.user_accounts.ports.outbound.user_repository import UserRepository


def summarize(user: User) -> AccountSummary:
    return AccountSummary(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
    )


class AccountAccessService(AccountAccess):
    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        unknown_email_attempts: UnknownEmailAttemptStore,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._unknown_attempts = unknown_email_attempts
        self._hasher = password_hasher
        self._now = clock
        self._dummy_hash: str | None = None

    def _compare_with_dummy(self, raw_password: str) -> None:
        """When the email does not exist, still spend the time of a real comparison, so response
        times do not reveal which emails are registered."""
        if self._dummy_hash is None:
            self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(16))
        self._hasher.matches(raw_password, self._dummy_hash)

    def _check_unknown_email(self, email: str, raw_password: str, now: datetime):
        """Same answers, at the same moments, as a real account (audit F-03a): otherwise the
        lockout message would reveal which emails are registered. Like a real locked account, a
        locked one is answered before comparing the password (same timing too)."""
        attempts = self._unknown_attempts.get(email)
        if attempts.is_locked(now):
            return CredentialCheckResult(
                CredentialCheckOutcome.LOCKED, locked_until=attempts.locked_until
            )
        self._compare_with_dummy(raw_password)
        locked_now = attempts.register_failure(now)
        self._unknown_attempts.save(email, attempts)
        if locked_now:
            # ``locked_now`` stays False: no account was locked, so the audit says LOGIN_FAILED.
            return CredentialCheckResult(
                CredentialCheckOutcome.LOCKED, locked_until=attempts.locked_until
            )
        return CredentialCheckResult(CredentialCheckOutcome.INVALID_CREDENTIALS)

    def check_credentials(self, email: str, raw_password: str) -> CredentialCheckResult:
        now = self._now()
        normalized = normalize_email(email)
        user = self._repository.get_by_email(normalized)
        if user is None:
            return self._check_unknown_email(normalized, raw_password, now)

        # FR-01-01 (corrected): a locked account is rejected before checking the password.
        if user.is_locked(now):
            return CredentialCheckResult(
                CredentialCheckOutcome.LOCKED, summarize(user), locked_until=user.locked_until
            )

        if not self._hasher.matches(raw_password, user.password_hash):
            locked_now = user.register_failed_login(now)
            self._repository.update(user)
            return CredentialCheckResult(
                CredentialCheckOutcome.LOCKED
                if locked_now
                else CredentialCheckOutcome.INVALID_CREDENTIALS,
                summarize(user),
                locked_until=user.locked_until if locked_now else None,
                locked_now=locked_now,
            )

        if not user.is_active:
            return CredentialCheckResult(CredentialCheckOutcome.INACTIVE, summarize(user))
        return CredentialCheckResult(CredentialCheckOutcome.SUCCESS, summarize(user))

    def register_failed_second_factor(self, user_id: UUID) -> FailedAttemptResult:
        user = self._repository.get_by_id(user_id)
        if user is None:
            return FailedAttemptResult(locked_now=False, locked_until=None)
        locked_now = user.register_failed_login(self._now())
        self._repository.update(user)
        return FailedAttemptResult(locked_now, user.locked_until if locked_now else None)

    def register_successful_login(self, user_id: UUID) -> None:
        user = self._repository.get_by_id(user_id)
        if user is not None:
            user.register_successful_login(self._now())
            self._repository.update(user)

    def get_account(self, user_id: UUID) -> AccountSummary | None:
        user = self._repository.get_by_id(user_id)
        return summarize(user) if user else None

    def is_locked(self, user_id: UUID) -> datetime | None:
        user = self._repository.get_by_id(user_id)
        if user is not None and user.is_locked(self._now()):
            return user.locked_until
        return None
