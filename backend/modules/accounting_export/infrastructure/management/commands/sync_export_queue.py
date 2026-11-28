"""Rebuilds the Odoo export queue from the work orders (step 5c decision).

    docker compose exec backend python manage.py sync_export_queue

Enqueues every "Pendiente" O.T. that is missing (e.g. generated before the queue existed, or if an
event was ever lost) and withdraws pending entries whose O.T. is no longer "Pendiente". It never
duplicates entries, so it can be run any number of times.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from modules.accounting_export.infrastructure.dependencies import export_queue_feed


class Command(BaseCommand):
    help = "Adds missing 'Pendiente' work orders to the Odoo export queue (safe to repeat)."

    def handle(self, *args, **options) -> None:
        with transaction.atomic():
            result = export_queue_feed().sync()
        self.stdout.write(
            self.style.SUCCESS(
                f"Export queue synced: {result.enqueued} enqueued, {result.withdrawn} withdrawn."
            )
        )
