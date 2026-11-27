"""Django ORM models of the Quotations module."""

import uuid

from django.db import models


class QuotationModel(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = "PENDING_REVIEW", "Pendiente de revisión"
        MODIFIED = "MODIFIED", "Modificada"
        APPROVED = "APPROVED", "Aprobada"
        REJECTED = "REJECTED", "Rechazada"

    class DispatchSource(models.TextChoices):
        SUGGESTED = "SUGGESTED"
        MANUAL = "MANUAL"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation_number = models.CharField(max_length=20, unique=True)
    customer_id = models.UUIDField(null=True, blank=True)  # customers module: plain UUID
    issued_at = models.DateTimeField()
    requester_full_name = models.CharField(max_length=150)
    requester_email = models.EmailField(max_length=254)
    requester_phone = models.CharField(max_length=30)
    requester_institution = models.CharField(max_length=200, blank=True, default="")
    requester_tax_id = models.CharField(max_length=20, blank=True, default="")
    currency = models.CharField(max_length=3, default="COP")
    commercial_terms = models.TextField(blank=True, default="")
    valid_until = models.DateField()
    estimated_dispatch_date = models.DateField(null=True, blank=True)
    dispatch_date_source = models.CharField(
        max_length=10, choices=DispatchSource.choices, blank=True, default=""
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    rejection_reason = models.TextField(blank=True, default="")
    access_key = models.CharField(max_length=64)
    # Stored totals so the review tray can filter by amount (US 2.26.4).
    estimated_total_min = models.DecimalField(
        max_digits=18, decimal_places=0, null=True, blank=True
    )
    estimated_total_max = models.DecimalField(
        max_digits=18, decimal_places=0, null=True, blank=True
    )
    final_total = models.DecimalField(max_digits=18, decimal_places=0, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by_id = models.UUIDField(null=True, blank=True)  # user_accounts: plain UUID
    approved_by_name = models.CharField(max_length=150, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "quotation"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["status", "-issued_at"], name="quotation_status_date_idx"),
            models.Index(fields=["customer_id"], name="quotation_customer_idx"),
        ]

    def __str__(self) -> str:
        return self.quotation_number


class QuotationItemModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(QuotationModel, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveSmallIntegerField(default=0)
    product_id = models.UUIDField()  # products module: plain UUID, with snapshots below
    product_code = models.CharField(max_length=30)
    description = models.CharField(max_length=200)
    unit_of_measure = models.CharField(max_length=30)
    quantity = models.PositiveIntegerField()
    unit_price_min = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    unit_price_max = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    final_unit_price = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    # Where the estimated range came from: HISTORY (statistics) or AI; empty = no estimate.
    price_source = models.CharField(max_length=10, blank=True, default="")

    class Meta:
        db_table = "quotation_item"
        ordering = ["position"]
        indexes = [models.Index(fields=["product_id"], name="quotation_item_product_idx")]

    def __str__(self) -> str:
        return f"{self.product_code} x {self.quantity}"


class QuotationCounterModel(models.Model):
    """Last quotation consecutive issued, global (never restarts). A single row, locked while a
    number is taken, so two requests never get the same one."""

    SINGLETON = 1

    id = models.PositiveSmallIntegerField(primary_key=True, default=SINGLETON)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "quotation_counter"

    def __str__(self) -> str:
        return str(self.last_number)
