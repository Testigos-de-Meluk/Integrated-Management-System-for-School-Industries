"""Django ORM models of the User Accounts module.

Roles are fixed (RN-M1-01): the role is a column and the role-permission matrix lives in code
(``shared_kernel.domain.security``), so there is no ROLE / ROLE_PERMISSION table to keep in sync.
"""

import uuid

from django.db import models


class UserModel(models.Model):
    class Role(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Superadministrador"
        ADMIN = "ADMIN", "Administrador"
        OPERATOR = "OPERATOR", "Operador"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Activo"
        INACTIVE = "INACTIVE", "Inactivo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(max_length=254, unique=True)  # stored lowercase by the domain
    job_title = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=Role.choices)
    password_hash = models.CharField(max_length=128)  # bcrypt, never exposed
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    last_access_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    last_failed_login_at = models.DateTimeField(null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_user"
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["role"], name="app_user_role_idx"),
            models.Index(fields=["status"], name="app_user_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"
