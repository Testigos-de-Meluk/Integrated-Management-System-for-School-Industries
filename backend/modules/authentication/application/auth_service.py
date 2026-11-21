"""Use cases of the Authentication module (implements ``AuthUseCases``).

The account itself (password, active status, failed-attempt counter and lockout) belongs to the
user accounts module; this service talks to it only through its ``AccountAccess`` inbound port.
"""

import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.authentication.domain.exceptions import (
    AccountInactive,
    AccountLocked,
    EnrollmentNotStarted,
    InvalidCredentials,
    InvalidVerificationCode,
    PreAuthExpired,
    SessionEnded,
    SessionExpired,
    SessionReplaced,
)
from modules.authentication.domain.session import Session, TerminationReason
from modules.authentication.domain.totp_enrollment import TotpEnrollment
from modules.authentication.ports.inbound.auth_use_cases import (
    AuthUseCases,
    CurrentUser,
    EnrollmentView,
    LoginChallenge,
    LoginStep,
    Outcome,
    SessionTokens,
)
from modules.authentication.ports.outbound.repositories import (
    EnrollmentRepository,
    SessionRepository,
)
from modules.authentication.ports.outbound.security import (
    PreAuthPurpose,
    TokenIssuer,
    TwoFactorProvider,
)
from modules.shared_kernel.domain.audit import ActorType, AuditAction, AuditRecord, OperationResult
from modules.shared_kernel.domain.exceptions import AuthenticationError, DomainError
from modules.shared_kernel.domain.security import DEFAULT_ROLE_PERMISSIONS, Actor, RoleType
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger
from modules.user_accounts.ports.inbound.account_access import (
    AccountAccess,
    AccountSummary,
    CredentialCheckOutcome,
)

_SESSION_ERRORS: dict[TerminationReason, type[AuthenticationError]] = {
    TerminationReason.NEW_LOGIN: SessionReplaced,
    TerminationReason.INACTIVITY: SessionExpired,
    TerminationReason.ACCOUNT_DEACTIVATED: AccountInactive,
}


class AuthService(AuthUseCases):
    def __init__(
        self,
        accounts: AccountAccess,
        sessions: SessionRepository,
        enrollments: EnrollmentRepository,
        tokens: TokenIssuer,
        two_factor: TwoFactorProvider,
        audit_logger: AuditLogger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._accounts = accounts
        self._sessions = sessions
        self._enrollments = enrollments
        self._tokens = tokens
        self._two_factor = two_factor
        self._audit = audit_logger
        self._now = clock

    # --- Step 1: email + password (FR-01-01) --------------------------------------------------

    def login(self, email: str, password: str, source_ip: str | None) -> Outcome[LoginChallenge]:
        now = self._now()
        check = self._accounts.check_credentials(email, password)
        account = check.account

        if check.outcome is not CredentialCheckOutcome.SUCCESS:
            error, reason = self._credential_error(check.outcome, check.locked_until, now)
            self._log_failure(
                AuditAction.ACCOUNT_LOCKED if check.locked_now else AuditAction.LOGIN_FAILED,
                account,
                email,
                source_ip,
                reason,
            )
            return Outcome.fail(error)

        enrollment = self._enrollments.get_for_user(account.id)
        purpose = (
            PreAuthPurpose.VERIFY_CODE
            if enrollment and enrollment.is_confirmed
            else PreAuthPurpose.ENROLL_AUTHENTICATOR
        )
        token = self._tokens.issue_pre_auth(account.id, purpose, now)
        return Outcome.ok(LoginChallenge(LoginStep(purpose.value), token.value, token.expires_at))

    # --- Step 2a: first login, link the authenticator (FR-01-02) -------------------------------

    def start_enrollment(self, pre_auth_token: str) -> EnrollmentView:
        now = self._now()
        account = self._account_from_pre_auth(pre_auth_token, PreAuthPurpose.ENROLL_AUTHENTICATOR)
        secret = self._two_factor.new_secret()
        enrollment = self._enrollments.get_for_user(account.id)
        if enrollment is None:
            enrollment = TotpEnrollment.start(account.id, secret, now)
        else:
            enrollment.restart(secret, now)  # raises AlreadyEnrolled if confirmed (US 1.2.6)
        self._enrollments.save(enrollment)
        return EnrollmentView(
            qr_code=self._two_factor.qr_code(secret, account.email),
            secret=secret,
            account_name=account.email,
            expires_at=enrollment.expires_at,
        )

    def confirm_enrollment(
        self, pre_auth_token: str, code: str, source_ip: str | None
    ) -> SessionTokens:
        now = self._now()
        account = self._account_from_pre_auth(pre_auth_token, PreAuthPurpose.ENROLL_AUTHENTICATOR)
        enrollment = self._enrollments.get_for_user(account.id)
        if enrollment is None:
            raise EnrollmentNotStarted()
        enrollment.ensure_can_be_confirmed(now)  # expired → "El tiempo de vinculación ha expirado"
        step = self._two_factor.matching_step(enrollment.secret, code, now)
        if step is None:
            raise InvalidVerificationCode()  # US 1.2.3: pairing stays pending, retries allowed
        enrollment.confirm(now, step)
        self._enrollments.save(enrollment)
        self._audit.log(
            AuditRecord(
                action=AuditAction.CREATED,
                entity_type="TOTPEnrollment",
                entity_id=str(enrollment.id),
                actor=Actor.for_role(RoleType(account.role), account.id, source_ip),
                new_values={"user_id": str(account.id), "status": enrollment.status.value},
            )
        )
        return self._open_session(account, source_ip, now)

    # --- Step 2b: every other login, 6-digit code (FR-01-03) -----------------------------------

    def verify_code(
        self, pre_auth_token: str, code: str, source_ip: str | None
    ) -> Outcome[SessionTokens]:
        now = self._now()
        try:
            account = self._account_from_pre_auth(pre_auth_token, PreAuthPurpose.VERIFY_CODE)
        except DomainError as error:
            return Outcome.fail(error)

        locked_until = self._accounts.is_locked(account.id)
        if locked_until is not None:
            return Outcome.fail(AccountLocked(locked_until, now))

        enrollment = self._enrollments.get_for_user(account.id)
        step = (
            self._two_factor.matching_step(enrollment.secret, code, now)
            if enrollment and enrollment.is_confirmed
            else None
        )
        if step is None or not enrollment.accept_code_step(step):
            failure = self._accounts.register_failed_second_factor(account.id)
            self._log_failure(
                AuditAction.ACCOUNT_LOCKED if failure.locked_now else AuditAction.LOGIN_FAILED,
                account,
                account.email,
                source_ip,
                "Código de verificación incorrecto",
            )
            if failure.locked_now:
                return Outcome.fail(AccountLocked(failure.locked_until, now))
            return Outcome.fail(InvalidVerificationCode())

        self._enrollments.save(enrollment)  # remember the used step (no code reuse)
        return Outcome.ok(self._open_session(account, source_ip, now))

    # --- Session lifecycle --------------------------------------------------------------------

    def refresh(self, refresh_token: str) -> Outcome[SessionTokens]:
        now = self._now()
        claims = self._tokens.read_refresh(refresh_token)
        session = self._sessions.get(claims.session_id) if claims else None
        if claims is None or session is None:
            return Outcome.fail(SessionEnded())
        if session.is_terminated:
            return Outcome.fail(self._error_for_terminated(session))
        if claims.token_id != session.refresh_token_id:
            # An old refresh token was replayed: someone may have stolen it. Close the session.
            self._terminate(session, TerminationReason.TOKEN_REUSE, now)
            return Outcome.fail(SessionEnded())
        if session.is_inactive(now):
            self._terminate(session, TerminationReason.INACTIVITY, now)
            return Outcome.fail(SessionExpired())

        account = self._accounts.get_account(session.user_id)
        if account is None or not account.is_active:
            self._terminate(session, TerminationReason.ACCOUNT_DEACTIVATED, now)
            return Outcome.fail(AccountInactive())

        session.rotate_refresh_token(secrets.token_urlsafe(24))
        self._sessions.update(session)
        return Outcome.ok(self._issue_tokens(account, session, now))

    def authenticate(self, access_token: str, source_ip: str | None) -> Actor:
        now = self._now()
        claims = self._tokens.read_access(access_token)
        session = self._sessions.get(claims.session_id) if claims else None
        if claims is None or session is None:
            raise AuthenticationError()
        if session.is_terminated:
            raise self._error_for_terminated(session)
        if session.is_inactive(now):
            raise SessionExpired()  # FR-01-06 (the refresh endpoint records the closure)

        account = self._accounts.get_account(session.user_id)
        if account is None or not account.is_active:
            raise AccountInactive()
        if session.touch(now):
            self._sessions.update(session)
        # The role is read from the account on every request, so role changes apply at once.
        return Actor.for_role(
            RoleType(account.role), user_id=account.id, source_ip=source_ip, session_id=session.id
        )

    def current_user(self, actor: Actor) -> CurrentUser:
        account = self._accounts.get_account(actor.user_id) if actor.user_id else None
        if account is None:
            raise AuthenticationError()
        return self._current_user(account)

    def logout(self, actor: Actor) -> None:
        session = self._sessions.get(actor.session_id) if actor.session_id else None
        if session is not None and not session.is_terminated:
            self._terminate(session, TerminationReason.LOGOUT, self._now(), actor=actor)

    def reset_authenticator(self, user_id: UUID) -> bool:
        return self._enrollments.delete_for_user(user_id)

    def terminate_sessions_for(self, user_id: UUID, reason: str) -> None:
        now = self._now()
        for session in self._sessions.active_sessions_of(user_id):
            self._terminate(session, TerminationReason(reason), now)

    # --- Helpers ------------------------------------------------------------------------------

    def _account_from_pre_auth(self, token: str, purpose: PreAuthPurpose) -> AccountSummary:
        claims = self._tokens.read_pre_auth(token)
        if claims is None or claims.purpose is not purpose:
            raise PreAuthExpired()
        account = self._accounts.get_account(claims.user_id)
        if account is None:
            raise PreAuthExpired()
        if not account.is_active:
            raise AccountInactive()
        return account

    def _open_session(
        self, account: AccountSummary, source_ip: str | None, now: datetime
    ) -> SessionTokens:
        # FR-01-05: a new login closes any other active session of the same account.
        for previous in self._sessions.active_sessions_of(account.id):
            self._terminate(previous, TerminationReason.NEW_LOGIN, now)

        session = Session.open(account.id, now, refresh_token_id=secrets.token_urlsafe(24))
        self._sessions.add(session)
        self._accounts.register_successful_login(account.id)
        self._audit.log(
            AuditRecord(
                action=AuditAction.LOGIN,
                entity_type="Session",
                entity_id=str(session.id),
                actor=Actor.for_role(
                    RoleType(account.role), account.id, source_ip, session_id=session.id
                ),
            )
        )
        return self._issue_tokens(account, session, now)

    def _issue_tokens(
        self, account: AccountSummary, session: Session, now: datetime
    ) -> SessionTokens:
        access = self._tokens.issue_access(account.id, session.id, now)
        refresh = self._tokens.issue_refresh(account.id, session.id, session.refresh_token_id, now)
        return SessionTokens(
            access_token=access.value,
            access_expires_at=access.expires_at,
            refresh_token=refresh.value,
            refresh_expires_at=refresh.expires_at,
            user=self._current_user(account),
        )

    def _terminate(
        self,
        session: Session,
        reason: TerminationReason,
        now: datetime,
        actor: Actor | None = None,
    ) -> None:
        session.terminate(reason, now)
        self._sessions.update(session)
        self._audit.log(
            AuditRecord(
                action=AuditAction.LOGOUT,
                entity_type="Session",
                entity_id=str(session.id),
                actor=actor,
                actor_type=ActorType.USER if actor else ActorType.SYSTEM,
                actor_label=None if actor else "session-control",
                new_values={"user_id": str(session.user_id), "reason": reason.value},
            )
        )

    @staticmethod
    def _current_user(account: AccountSummary) -> CurrentUser:
        role = RoleType(account.role)
        return CurrentUser(
            id=account.id,
            full_name=account.full_name,
            email=account.email,
            role=role.value,
            permissions=tuple(sorted(p.value for p in DEFAULT_ROLE_PERMISSIONS[role])),
        )

    @staticmethod
    def _error_for_terminated(session: Session) -> AuthenticationError:
        error_type = _SESSION_ERRORS.get(session.termination_reason, SessionEnded)
        return error_type()

    @staticmethod
    def _credential_error(
        outcome: CredentialCheckOutcome, locked_until: datetime | None, now: datetime
    ) -> tuple[DomainError, str]:
        if outcome is CredentialCheckOutcome.LOCKED:
            return AccountLocked(locked_until, now), "Cuenta bloqueada"
        if outcome is CredentialCheckOutcome.INACTIVE:
            return AccountInactive(), "Cuenta inactiva"
        return InvalidCredentials(), "Credenciales inválidas"

    def _log_failure(
        self,
        action: AuditAction,
        account: AccountSummary | None,
        attempted_email: str,
        source_ip: str | None,
        reason: str,
    ) -> None:
        self._audit.log(
            AuditRecord(
                action=action,
                entity_type="User",
                entity_id=str(account.id) if account else "-",
                actor=None,
                actor_type=ActorType.ANONYMOUS,
                actor_label=attempted_email.strip().lower()[:254],
                source_ip=source_ip,
                reason=reason,
                result=OperationResult.FAILURE,
            )
        )
