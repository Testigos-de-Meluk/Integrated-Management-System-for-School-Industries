"""Creates the first Superadministrador account (bootstrap).

Only administrators can create accounts, so the very first one has to be created from the
command line:

    docker compose exec backend python manage.py create_superadmin \
        --email admin@industriasescolares.com --name "Carlos Ríos" --job-title "Soporte de sistemas"

A random password that satisfies the policy is generated and printed once (unless --password is
given). On the first login the user links an authenticator app, like any other account.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from modules.shared_kernel.domain.audit import ActorType, AuditAction, AuditRecord
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.security import RoleType
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger
from modules.user_accounts.domain.password_policy import PasswordPolicy
from modules.user_accounts.domain.user import User, normalize_email
from modules.user_accounts.infrastructure.dependencies import password_hasher
from modules.user_accounts.infrastructure.persistence.django_user_repository import (
    DjangoUserRepository,
)


class Command(BaseCommand):
    help = "Creates a Superadministrador account and prints its initial password."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True, help="Full name")
        parser.add_argument("--job-title", default="Superadministrador")
        parser.add_argument("--password", help="Initial password (generated if omitted)")

    @transaction.atomic
    def handle(self, *args, **options):
        repository = DjangoUserRepository()
        policy = PasswordPolicy()
        email = normalize_email(options["email"])
        if repository.exists_with_email(email):
            raise CommandError(f"Ya existe una cuenta con el correo {email}.")

        raw_password = options["password"] or policy.generate()
        try:
            policy.validate(raw_password)
            user = User.register(
                options["name"],
                email,
                options["job_title"],
                RoleType.SUPERADMIN,
                password_hasher().hash(raw_password),
            )
        except ValidationError as error:
            raise CommandError(f"{error.message} {error.errors}") from error

        repository.add(user)
        DatabaseAuditLogger().log(
            AuditRecord(
                action=AuditAction.CREATED,
                entity_type="User",
                entity_id=str(user.id),
                actor=None,
                actor_type=ActorType.SYSTEM,
                actor_label="create_superadmin",
                new_values=user.snapshot(),
            )
        )

        self.stdout.write(self.style.SUCCESS(f"Superadministrador creado: {user.email}"))
        if not options["password"]:
            self.stdout.write(f"Contraseña inicial (se muestra una sola vez): {raw_password}")
