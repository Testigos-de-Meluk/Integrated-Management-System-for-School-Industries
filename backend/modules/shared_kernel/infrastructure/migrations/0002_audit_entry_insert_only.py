"""Makes ``audit_entry`` insert-only at database level (NFR-08-01).

The trigger rejects UPDATE and DELETE for every database user, including the application's own,
so not even a Superadministrador (or a bug) can alter or erase the audit log. Only PostgreSQL is
protected; the optional SQLite test mode skips it.

Note: the SQL avoids the ``%`` character on purpose. psycopg treats it as a query placeholder, so
the error message is built with ``||`` instead of ``RAISE EXCEPTION '... % ...', TG_OP``.
"""

from django.db import migrations

CREATE_STATEMENTS = [
    """
    CREATE OR REPLACE FUNCTION audit_entry_reject_changes() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION USING MESSAGE = 'audit_entry is insert-only: ' || TG_OP || ' is not allowed';
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER audit_entry_insert_only
    BEFORE UPDATE OR DELETE ON audit_entry
    FOR EACH ROW EXECUTE FUNCTION audit_entry_reject_changes()
    """,
]

DROP_STATEMENTS = [
    "DROP TRIGGER IF EXISTS audit_entry_insert_only ON audit_entry",
    "DROP FUNCTION IF EXISTS audit_entry_reject_changes()",
]


def _run(statements):
    def operation(apps, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        for statement in statements:
            schema_editor.execute(statement, params=None)

    return operation


class Migration(migrations.Migration):
    dependencies = [("shared_kernel", "0001_initial")]

    operations = [migrations.RunPython(_run(CREATE_STATEMENTS), _run(DROP_STATEMENTS))]
