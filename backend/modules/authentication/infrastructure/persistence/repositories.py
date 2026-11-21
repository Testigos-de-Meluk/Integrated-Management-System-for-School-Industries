"""PostgreSQL adapters for sessions and TOTP enrollments."""

import base64
import hashlib
from functools import lru_cache
from uuid import UUID

from cryptography.fernet import Fernet
from django.conf import settings

from modules.authentication.domain.session import Session, SessionStatus, TerminationReason
from modules.authentication.domain.totp_enrollment import EnrollmentStatus, TotpEnrollment
from modules.authentication.infrastructure.models import SessionModel, TotpEnrollmentModel
from modules.authentication.ports.outbound.repositories import (
    EnrollmentRepository,
    SessionRepository,
)

# --- Sessions ---------------------------------------------------------------------------------


def _session_to_domain(model: SessionModel) -> Session:
    return Session(
        id=model.id,
        user_id=model.user_id,
        created_at=model.created_at,
        last_activity_at=model.last_activity_at,
        refresh_token_id=model.refresh_token_id,
        status=SessionStatus(model.status),
        termination_reason=(
            TerminationReason(model.termination_reason) if model.termination_reason else None
        ),
        terminated_at=model.terminated_at,
    )


def _apply_session(session: Session, model: SessionModel) -> SessionModel:
    model.id = session.id
    model.user_id = session.user_id
    model.created_at = session.created_at
    model.last_activity_at = session.last_activity_at
    model.refresh_token_id = session.refresh_token_id
    model.status = session.status.value
    model.termination_reason = (
        session.termination_reason.value if session.termination_reason else ""
    )
    model.terminated_at = session.terminated_at
    return model


class DjangoSessionRepository(SessionRepository):
    def get(self, session_id: UUID) -> Session | None:
        model = SessionModel.objects.filter(pk=session_id).first()
        return _session_to_domain(model) if model else None

    def add(self, session: Session) -> None:
        _apply_session(session, SessionModel()).save(force_insert=True)

    def update(self, session: Session) -> None:
        _apply_session(session, SessionModel.objects.get(pk=session.id)).save()

    def active_sessions_of(self, user_id: UUID) -> list[Session]:
        models = SessionModel.objects.filter(user_id=user_id, status=SessionModel.Status.ACTIVE)
        return [_session_to_domain(m) for m in models]


# --- TOTP enrollments (secret encrypted at rest) ----------------------------------------------


@lru_cache(maxsize=1)
def _cipher() -> Fernet:
    """``TOTP_ENCRYPTION_KEY`` must be a Fernet key in production. In development it falls back
    to a key derived from ``SECRET_KEY``."""
    key = settings.TOTP_ENCRYPTION_KEY
    if not key:
        digest = hashlib.sha256(f"totp:{settings.SECRET_KEY}".encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key)


def _enrollment_to_domain(model: TotpEnrollmentModel) -> TotpEnrollment:
    return TotpEnrollment(
        id=model.id,
        user_id=model.user_id,
        secret=_cipher().decrypt(model.encrypted_secret.encode()).decode(),
        issued_at=model.issued_at,
        expires_at=model.expires_at,
        status=EnrollmentStatus(model.status),
        confirmed_at=model.confirmed_at,
        last_used_step=model.last_used_step,
    )


class DjangoEnrollmentRepository(EnrollmentRepository):
    def get_for_user(self, user_id: UUID) -> TotpEnrollment | None:
        model = TotpEnrollmentModel.objects.filter(user_id=user_id).first()
        return _enrollment_to_domain(model) if model else None

    def save(self, enrollment: TotpEnrollment) -> None:
        TotpEnrollmentModel.objects.update_or_create(
            user_id=enrollment.user_id,
            defaults={
                "id": enrollment.id,
                "encrypted_secret": _cipher().encrypt(enrollment.secret.encode()).decode(),
                "issued_at": enrollment.issued_at,
                "expires_at": enrollment.expires_at,
                "status": enrollment.status.value,
                "confirmed_at": enrollment.confirmed_at,
                "last_used_step": enrollment.last_used_step,
            },
        )
