"""Removes UPDATE/DELETE privileges of ``PUBLIC`` on ``audit_entry`` (NFR-08-01).

What this does NOT do: by default ``PUBLIC`` has no privileges on a table, so in a fresh
database this statement changes nothing (checked: ``relacl`` was empty). It only matters if
someone granted them to ``PUBLIC`` by hand. It does not restrict the table owner either, and in
development the application connects as the owner (and superuser), who can also disable the
triggers of 0002/0004.

The real second layer is a deployment decision: the application must connect with a role that
does not own the table and has only ``SELECT, INSERT`` on ``audit_entry`` (pending item in
CLAUDE.md). This migration is kept because it is harmless and already published.

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
