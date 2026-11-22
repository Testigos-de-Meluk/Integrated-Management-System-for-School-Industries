"""Django ORM models of the Customers module."""

import uuid

from django.db import models


class CustomerModel(models.Model):
    class Type(models.TextChoices):
        NATURAL_PERSON = "NATURAL_PERSON", "Persona natural"
        LEGAL_ENTITY = "LEGAL_ENTITY", "Persona jurídica"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        INACTIVE = "INACTIVE", "Inactivo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_type = models.CharField(max_length=20, choices=Type.choices)
    tax_id = models.CharField(max_length=20, unique=True)  # normalized by the domain
    name = models.CharField(max_length=200)  # full name or business name
    address = models.CharField(max_length=250)
    primary_phone = models.CharField(max_length=30)
    email = models.EmailField(max_length=254)
    commercial_contact = models.CharField(max_length=150, blank=True, default="")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status"], name="customer_status_idx"),
            models.Index(fields=["name"], name="customer_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.tax_id})"


class CommercialNoteModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(CustomerModel, on_delete=models.PROTECT, related_name="notes")
    author_id = models.UUIDField()  # account of another module: plain UUID, not a foreign key
    author_name = models.CharField(max_length=150)
    content = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField(null=True, blank=True)
    updated_by_id = models.UUIDField(null=True, blank=True)
    updated_by_name = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        db_table = "commercial_note"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer", "-created_at"], name="note_customer_date_idx")]

    def __str__(self) -> str:
        return f"Note {self.id} on {self.customer_id}"
