"""``UnknownEmailAttemptStore`` on the Django cache (Redis in Docker).

The key is an HMAC of the email with ``SECRET_KEY``, so Redis never holds the address itself. An
entry lives while it is needed: the lock duration while locked, otherwise one day (a real
account's counter has no expiry, but a day is far longer than any guessing session).
"""

import hashlib
import hmac
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache

from modules.user_accounts.domain.unknown_email_attempts import UnknownEmailAttempts
from modules.user_accounts.ports.outbound.unknown_email_attempt_store import (
    UnknownEmailAttemptStore,
)

_PREFIX = "login-unknown-email"
_IDLE_TTL_SECONDS = 24 * 60 * 60


def _key(email: str) -> str:
    digest = hmac.new(settings.SECRET_KEY.encode(), email.encode(), hashlib.sha256).hexdigest()
    return f"{_PREFIX}:{digest}"


class CacheUnknownEmailAttemptStore(UnknownEmailAttemptStore):
    def get(self, email: str) -> UnknownEmailAttempts:
        value = cache.get(_key(email))
        if not value:
            return UnknownEmailAttempts()
        failures, locked_until = value
        return UnknownEmailAttempts(
            failures, datetime.fromisoformat(locked_until) if locked_until else None
        )

    def save(self, email: str, attempts: UnknownEmailAttempts) -> None:
        ttl = _IDLE_TTL_SECONDS
        if attempts.locked_until is not None:
            remaining = (attempts.locked_until - datetime.now(UTC)).total_seconds()
            ttl = max(1, int(remaining) + 1)
        locked = attempts.locked_until.isoformat() if attempts.locked_until else None
        cache.set(_key(email), (attempts.failures, locked), timeout=ttl)
