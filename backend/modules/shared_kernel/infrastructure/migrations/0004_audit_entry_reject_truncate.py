"""Also rejects ``TRUNCATE`` on ``audit_entry`` (NFR-08-01).

The row trigger of migration 0002 covers UPDATE and DELETE, but row triggers never fire on
TRUNCATE: a single ``TRUNCATE audit_entry`` would have emptied the log. This adds a statement-level
trigger with the same function, so the error message is the same ("... TRUNCATE is not allowed").

Like 0002, it does not stop the table owner or a superuser, who can disable triggers; that needs
the application to connect with a role that does not own the table (see CLAUDE.md, pending items).
"""

from django.db import migrations

CREATE_STATEMENTS = [
    """
    CREATE TRIGGER audit_entry_no_truncate
    BEFORE TRUNCATE ON audit_entry
    FOR EACH STATEMENT EXECUTE FUNCTION audit_entry_reject_changes()
    """,
]

DROP_STATEMENTS = ["DROP TRIGGER IF EXISTS audit_entry_no_truncate ON audit_entry"]


def _run(statements):
    def operation(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        for statement in statements:
            schema_editor.execute(statement, params=None)

    return operation


class Migration(migrations.Migration):
    dependencies = [("shared_kernel", "0003_audit_entry_revoke_writes")]

    operations = [migrations.RunPython(_run(CREATE_STATEMENTS), _run(DROP_STATEMENTS))]
