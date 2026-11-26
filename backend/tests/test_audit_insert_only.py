"""NFR-08-01: the audit log cannot be modified or deleted, not even by the application."""

import pytest
from django.db import DatabaseError, connection, transaction

from modules.shared_kernel.infrastructure.models import AuditEntryModel

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="The trigger only exists in PostgreSQL"
    ),
]


@pytest.fixture
def entry():
    return AuditEntryModel.objects.create(
        actor_type="SYSTEM", action="CREATED", entity_type="Test", entity_id="1"
    )


def test_update_is_rejected(entry):
    with pytest.raises(DatabaseError), transaction.atomic():
        AuditEntryModel.objects.filter(pk=entry.pk).update(reason="tampered")


def test_delete_is_rejected(entry):
    with pytest.raises(DatabaseError), transaction.atomic():
        AuditEntryModel.objects.filter(pk=entry.pk).delete()


def test_truncate_is_rejected(entry):
    """Row triggers do not fire on TRUNCATE: migration 0004 adds a statement-level one."""
    with pytest.raises(DatabaseError, match="TRUNCATE is not allowed"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE audit_entry")
    assert AuditEntryModel.objects.filter(pk=entry.pk).exists()
