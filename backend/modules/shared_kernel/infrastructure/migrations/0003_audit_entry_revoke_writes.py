"""Removes UPDATE/DELETE privileges on ``audit_entry`` (NFR-08-01, second layer).

Migration 0002 created the trigger that rejects UPDATE and DELETE. The trigger protects every
path that goes through the table, but a role that owns the table can drop it. This migration
takes the privilege away from ``PUBLIC`` as well, so a forgotten role cannot even try; the owner
still can, which is why both layers exist.

Reversal is a no-op on purpose: the previous privileges of an arbitrary deployment are unknown,
and granting them back would open a hole that was closed for a reason.
"""

from django.db import migrations

REVOKE_STATEMENTS = [
    "REVOKE UPDATE, DELETE ON audit_entry FROM PUBLIC",
]


def _revoke(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for statement in REVOKE_STATEMENTS:
        schema_editor.execute(statement, params=None)


class Migration(migrations.Migration):
    dependencies = [("shared_kernel", "0002_audit_entry_insert_only")]

    operations = [migrations.RunPython(_revoke, migrations.RunPython.noop)]
