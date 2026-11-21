"""Makes ``audit_entry`` insert-only at database level (NFR-08-01).

The trigger rejects UPDATE and DELETE for every database user, including the application's own,
so not even a Superadministrador (or a bug) can alter or erase the audit log. Only PostgreSQL is
protected; the optional SQLite test mode skips it.
"""

from django.db import migrations

CREATE_SQL = """
CREATE OR REPLACE FUNCTION audit_entry_reject_changes() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_entry is insert-only: % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_entry_insert_only
BEFORE UPDATE OR DELETE ON audit_entry
FOR EACH ROW EXECUTE FUNCTION audit_entry_reject_changes();
"""

DROP_SQL = """
DROP TRIGGER IF EXISTS audit_entry_insert_only ON audit_entry;
DROP FUNCTION IF EXISTS audit_entry_reject_changes();
"""


def _run(sql):
    def operation(apps, schema_editor):
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(sql)

    return operation


class Migration(migrations.Migration):
    dependencies = [("shared_kernel", "0001_initial")]

    operations = [migrations.RunPython(_run(CREATE_SQL), _run(DROP_SQL))]
