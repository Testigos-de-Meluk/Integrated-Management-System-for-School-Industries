"""Composition root of the Authentication module."""

from datetime import timedelta
from functools import lru_cache

from django.conf import settings

from modules.authentication.application.auth_service import AuthService
from modules.authentication.ports.inbound.auth_use_cases import AuthUseCases
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger
from modules.user_accounts.infrastructure.dependencies import account_access

from .persistence.repositories import DjangoEnrollmentRepository, DjangoSessionRepository
from .security.jwt_token_issuer import JwtTokenIssuer
from .security.pyotp_two_factor_provider import PyotpTwoFactorProvider


@lru_cache(maxsize=1)
def auth_use_cases() -> AuthUseCases:
    return AuthService(
        accounts=account_access(),  # inbound port of the user accounts module
        sessions=DjangoSessionRepository(),
        enrollments=DjangoEnrollmentRepository(),
        tokens=JwtTokenIssuer(
            signing_key=settings.JWT_SIGNING_KEY,
            access_ttl=timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
            refresh_ttl=timedelta(hours=settings.REFRESH_TOKEN_HOURS),
        ),
        two_factor=PyotpTwoFactorProvider(),
        audit_logger=DatabaseAuditLogger(),
    )
