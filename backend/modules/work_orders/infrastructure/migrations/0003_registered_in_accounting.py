"""Siigo → Odoo (team decision with Industrias Escolares, November 2026).

The status stored as ``REGISTERED_IN_SIIGO`` becomes the neutral ``REGISTERED_IN_ACCOUNTING``
(shown as "Registrada en Odoo"), so a future change of accounting system only changes labels. The
column grows to 30 characters to fit the new value. Reversible.
"""

from django.db import migrations, models

OLD = "REGISTERED_IN_SIIGO"
NEW = "REGISTERED_IN_ACCOUNTING"


def rename_forward(apps, schema_editor):
    apps.get_model("work_orders", "WorkOrderModel").objects.filter(status=OLD).update(status=NEW)


def rename_backward(apps, schema_editor):
    apps.get_model("work_orders", "WorkOrderModel").objects.filter(status=NEW).update(status=OLD)


class Migration(migrations.Migration):
    dependencies = [
        ("work_orders", "0002_quotation_approved_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="workordermodel",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pendiente"),
                    ("REGISTERED_IN_ACCOUNTING", "Registrada en Odoo"),
                    ("RECONCILED", "Conciliada"),
                    ("CANCELLED", "Anulada"),
                ],
                default="PENDING",
                max_length=30,
            ),
        ),
        migrations.RunPython(rename_forward, rename_backward),
    ]
