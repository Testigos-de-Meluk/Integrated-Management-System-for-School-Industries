"""Pure domain and token tests (no database)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from modules.authentication.domain.exceptions import AlreadyEnrolled, EnrollmentExpired
from modules.authentication.domain.session import Session, TerminationReason
from modules.authentication.domain.totp_enrollment import EnrollmentStatus, TotpEnrollment
from modules.authentication.infrastructure.security.jwt_token_issuer import JwtTokenIssuer
from modules.authentication.ports.outbound.security import PreAuthPurpose

NOW = datetime.now(UTC)


def test_session_expires_after_15_minutes_without_activity():
    session = Session.open(uuid4(), NOW, "r1")

    assert not session.is_inactive(NOW + timedelta(minutes=14, seconds=59))
    assert session.is_inactive(NOW + timedelta(minutes=15))


def test_activity_is_written_at_most_every_30_seconds():
    session = Session.open(uuid4(), NOW, "r1")

    assert session.touch(NOW + timedelta(seconds=10)) is False
    assert session.touch(NOW + timedelta(seconds=40)) is True
    assert not session.is_inactive(NOW + timedelta(minutes=15, seconds=30))


def test_terminate_keeps_the_first_reason():
    session = Session.open(uuid4(), NOW, "r1")

    session.terminate(TerminationReason.NEW_LOGIN, NOW)
    session.terminate(TerminationReason.LOGOUT, NOW)

    assert session.termination_reason is TerminationReason.NEW_LOGIN


def test_enrollment_expires_after_5_minutes_and_can_be_restarted():
    enrollment = TotpEnrollment.start(uuid4(), "SECRET1", NOW)

    with pytest.raises(EnrollmentExpired):
        enrollment.confirm(NOW + timedelta(minutes=5), step=1)
    assert enrollment.status is EnrollmentStatus.EXPIRED

    enrollment.restart("SECRET2", NOW + timedelta(minutes=6))
    enrollment.confirm(NOW + timedelta(minutes=7), step=1)
    assert enrollment.is_confirmed


def test_confirmed_enrollment_cannot_be_restarted():
    enrollment = TotpEnrollment.start(uuid4(), "SECRET", NOW)
    enrollment.confirm(NOW, step=1)

    with pytest.raises(AlreadyEnrolled):
        enrollment.restart("OTHER", NOW)


def test_a_code_step_cannot_be_reused():
    enrollment = TotpEnrollment.start(uuid4(), "SECRET", NOW)
    enrollment.confirm(NOW, step=100)

    assert enrollment.accept_code_step(100) is False
    assert enrollment.accept_code_step(101) is True
    assert enrollment.accept_code_step(101) is False


def test_tokens_cannot_be_used_for_another_purpose():
    issuer = JwtTokenIssuer("k" * 32)
    user_id, session_id = uuid4(), uuid4()
    pre_auth = issuer.issue_pre_auth(user_id, PreAuthPurpose.VERIFY_CODE, NOW).value
    access = issuer.issue_access(user_id, session_id, NOW).value

    assert issuer.read_access(pre_auth) is None  # US 1.3.4
    assert issuer.read_refresh(access) is None
    assert issuer.read_access(access).session_id == session_id


def test_expired_or_tampered_tokens_are_rejected():
    issuer = JwtTokenIssuer("k" * 32, access_ttl=timedelta(minutes=5))
    old = issuer.issue_access(uuid4(), uuid4(), NOW - timedelta(minutes=6)).value
    valid = issuer.issue_access(uuid4(), uuid4(), NOW).value

    assert issuer.read_access(old) is None
    assert JwtTokenIssuer("another-key" * 3).read_access(valid) is None
