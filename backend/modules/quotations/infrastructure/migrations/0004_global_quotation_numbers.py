"""Quotation numbers change from ``COT-2026-0001`` (per year) to ``COT-20261127-00001`` (local
issue date + global consecutive that never restarts; corrections README, summary item 16).

Existing quotations are renumbered in issue order and the counter is left at the last number used,
so the next quotation never repeats one. On an empty database (a new environment) there is nothing
to renumber and the counter starts at 0. It uses the historical models of this migration, never
the app code, so it keeps working if the code changes later. The reverse step only restores the
old table: the old numbers are not recovered.
"""

from zoneinfo import ZoneInfo

from django.db import migrations, models

BUSINESS_TIMEZONE = ZoneInfo("America/Bogota")


def renumber(apps, schema_editor):
    quotation_model = apps.get_model("quotations", "QuotationModel")
    counter_model = apps.get_model("quotations", "QuotationCounterModel")
    last = 0
    for last, quotation in enumerate(
        quotation_model.objects.order_by("issued_at", "id").only("id", "issued_at"), start=1
    ):
        local_date = quotation.issued_at.astimezone(BUSINESS_TIMEZONE).date()
        quotation_model.objects.filter(pk=quotation.pk).update(
            quotation_number=f"COT-{local_date:%Y%m%d}-{last:05d}"
        )
    counter_model.objects.update_or_create(pk=1, defaults={"last_number": last})


class Migration(migrations.Migration):
    dependencies = [("quotations", "0003_item_price_source")]

    operations = [
        migrations.CreateModel(
            name="QuotationCounterModel",
            fields=[
                (
                    "id",
                    models.PositiveSmallIntegerField(default=1, primary_key=True, serialize=False),
                ),
                ("last_number", models.PositiveIntegerField(default=0)),
            ],
            options={"db_table": "quotation_counter"},
        ),
        migrations.RunPython(renumber, migrations.RunPython.noop),
        migrations.DeleteModel(name="QuotationSequenceModel"),
    ]
