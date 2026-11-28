"""Django ORM models of the Work Orders module.

They are persistence details: repositories in ``persistence/`` map them to and from domain
entities, so they never leave the infrastructure layer. Other modules are referenced by plain UUIDs
(quotation, customer, product, user) plus snapshots, never by foreign keys to their tables.
"""

import uuid

from django.db import models
from django.db.models import Q


class WorkOrderModel(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        REGISTERED_IN_ACCOUNTING = "REGISTERED_IN_ACCOUNTING", "Registrada en Odoo"
        RECONCILED = "RECONCILED", "Conciliada"
        CANCELLED = "CANCELLED", "Anulada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True)
    quotation_id = models.UUIDField()  # quotations module
    quotation_number = models.CharField(max_length=20)  # snapshot
    # Snapshot: the dispatch lead time is measured from the approval (FR-02-06). Null only for
    # O.T.s generated before step 5b (they are left out of the median).
    quotation_approved_at = models.DateTimeField(null=True, blank=True)
    customer_id = models.UUIDField()  # customers module
    customer_tax_id = models.CharField(max_length=20)  # snapshot
    customer_name = models.CharField(max_length=200)  # snapshot
    agreed_delivery_date = models.DateField()
    actual_dispatch_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.PENDING)
    cancellation_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField()
    created_by_id = models.UUIDField(null=True, blank=True)  # user_accounts module
    created_by_name = models.CharField(max_length=150, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order"
        ordering = ["-created_at"]
        constraints = [
            # One active O.T. per quotation; an annulled one does not count (summary item 1).
            models.UniqueConstraint(
                fields=["quotation_id"],
                condition=~Q(status="CANCELLED"),
                name="work_order_one_active_per_quotation",
            ),
            models.CheckConstraint(
                condition=~Q(status="RECONCILED") | Q(actual_dispatch_date__isnull=False),
                name="work_order_reconciled_has_dispatch_date",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="work_order_status_date_idx"),
            models.Index(fields=["customer_id"], name="work_order_customer_idx"),
            models.Index(fields=["quotation_id"], name="work_order_quotation_idx"),
        ]

    def __str__(self) -> str:
        return self.order_number


class WorkOrderItemModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    work_order = models.ForeignKey(WorkOrderModel, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveSmallIntegerField(default=0)
    product_id = models.UUIDField()  # products module: plain UUID, with snapshots below
    product_code = models.CharField(max_length=30)
    description = models.CharField(max_length=200)
    unit_of_measure = models.CharField(max_length=30)
    quantity = models.PositiveIntegerField()

    class Meta:
        db_table = "work_order_item"
        ordering = ["position"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="work_order_item_quantity")
        ]
        indexes = [models.Index(fields=["product_id"], name="work_order_item_product_idx")]

    def __str__(self) -> str:
        return f"{self.product_code} x {self.quantity}"


class WorkOrderCounterModel(models.Model):
    """Last O.T. consecutive issued, global (never restarts). A single row, locked while a number
    is taken, so two requests never get the same one."""

    SINGLETON = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "work_order_counter"

    def __str__(self) -> str:
        return str(self.last_number)
