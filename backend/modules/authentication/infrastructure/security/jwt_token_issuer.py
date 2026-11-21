"""``TokenIssuer`` implemented with PyJWT (HS256).

Each token has a ``typ`` claim, so a pre-authentication token can never be used as an access
token (US 1.3.4) and an access token can never be used to refresh.
"""

from datetime import datetime, timedelta
from uuid import UUID

import jwt

from modules.authentication.ports.outbound.security import (
    AccessClaims,
    IssuedToken,
    PreAuthClaims,
    PreAuthPurpose,
    RefreshClaims,
    TokenIssuer,
)

ISSUER = "imsi"
ALGORITHM = "HS256"


class JwtTokenIssuer(TokenIssuer):
    def __init__(
        self,
        signing_key: str,
        access_ttl: timedelta = timedelta(minutes=5),
        refresh_ttl: timedelta = timedelta(hours=12),
        pre_auth_ttl: timedelta = timedelta(minutes=10),
    ) -> None:
        self._key = signing_key
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl
        self._pre_auth_ttl = pre_auth_ttl

    # --- Issue --------------------------------------------------------------------------------

    def _issue(self, claims: dict, now: datetime, ttl: timedelta) -> IssuedToken:
        expires_at = now + ttl
        payload = {"iss": ISSUER, "iat": now, "exp": expires_at, **claims}
        return IssuedToken(jwt.encode(payload, self._key, algorithm=ALGORITHM), expires_at)

    def issue_pre_auth(self, user_id: UUID, purpose: PreAuthPurpose, now: datetime) -> IssuedToken:
        claims = {"typ": "pre_auth", "sub": str(user_id), "purpose": purpose.value}
        return self._issue(claims, now, self._pre_auth_ttl)

    def issue_access(self, user_id: UUID, session_id: UUID, now: datetime) -> IssuedToken:
        claims = {"typ": "access", "sub": str(user_id), "sid": str(session_id)}
        return self._issue(claims, now, self._access_ttl)

    def issue_refresh(
        self, user_id: UUID, session_id: UUID, token_id: str, now: datetime
    ) -> IssuedToken:
        claims = {"typ": "refresh", "sub": str(user_id), "sid": str(session_id), "jti": token_id}
        return self._issue(claims, now, self._refresh_ttl)

    # --- Read ---------------------------------------------------------------------------------

    def _read(self, token: str, token_type: str) -> dict | None:
        try:
            payload = jwt.decode(
                token,
                self._key,
                algorithms=[ALGORITHM],  # never accept "none" or another algorithm
                issuer=ISSUER,
                options={"require": ["exp", "iat", "sub", "typ"]},
            )
        except jwt.PyJWTError:
            return None
        return payload if payload.get("typ") == token_type else None

    def read_pre_auth(self, token: str) -> PreAuthClaims | None:
        payload = self._read(token, "pre_auth")
        if payload is None:
            return None
        try:
            return PreAuthClaims(UUID(payload["sub"]), PreAuthPurpose(payload["purpose"]))
        except (KeyError, ValueError):
            return None

    def read_access(self, token: str) -> AccessClaims | None:
        payload = self._read(token, "access")
        try:
            return AccessClaims(UUID(payload["sub"]), UUID(payload["sid"])) if payload else None
        except (KeyError, ValueError):
            return None

    def read_refresh(self, token: str) -> RefreshClaims | None:
        payload = self._read(token, "refresh")
        try:
            return (
                RefreshClaims(UUID(payload["sub"]), UUID(payload["sid"]), payload["jti"])
                if payload
                else None
            )
        except (KeyError, ValueError):
            return None
