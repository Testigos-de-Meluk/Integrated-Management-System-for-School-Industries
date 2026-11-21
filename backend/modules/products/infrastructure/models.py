"""Django ORM models of the Products module.

They are persistence details: ``persistence/`` maps them to and from the ``Product`` domain
entity, so they never leave the infrastructure layer.
"""

import uuid

from django.db import models


class ProductModel(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        INACTIVE = "INACTIVE", "Inactivo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200)
    unit_of_measure = models.CharField(max_length=30)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["status"], name="product_status_idx"),
            models.Index(fields=["unit_of_measure"], name="product_unit_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"
