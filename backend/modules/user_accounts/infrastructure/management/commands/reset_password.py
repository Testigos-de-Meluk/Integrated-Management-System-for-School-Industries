"""Sets a new password for an account from the command line (recovery).

Useful when the initial password printed by ``create_superadmin`` was lost, or when no
administrator can log in. Passwords are stored as bcrypt hashes, so they can never be read back;
they can only be replaced:

    docker compose exec backend python manage.py reset_password --email admin@empresa.com

A new random password is generated and printed once (unless --password is given). The account is
also unlocked and its open sessions are closed. With --reset-authenticator the authenticator app
must be linked again on the next login (e.g. the phone was lost).
"""

from datetime import UTC, datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from modules.shared_kernel.domain.audit import ActorType, AuditAction, AuditRecord
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger
from modules.shared_kernel.infrastructure.events.in_process_event_bus import event_bus
from modules.user_accounts.domain.events import UserPasswordChanged
from modules.user_accounts.domain.password_policy import PasswordPolicy
from modules.user_accounts.domain.user import normalize_email
from modules.user_accounts.infrastructure.dependencies import password_hasher
from modules.user_accounts.infrastructure.persistence.django_user_repository import (
    DjangoUserRepository,
)


class Command(BaseCommand):
    help = "Sets a new password for an account and prints it once."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", help="New password (generated if omitted)")
        parser.add_argument(
            "--reset-authenticator",
            action="store_true",
            help="Unlink the authenticator app: it must be linked again on the next login.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        repository = DjangoUserRepository()
        policy = PasswordPolicy()
        user = repository.get_by_email(normalize_email(options["email"]))
        if user is None:
            raise CommandError(f"No existe una cuenta con el correo {options['email']}.")

        raw_password = options["password"] or policy.generate()
        try:
            policy.validate(raw_password)
        except ValidationError as error:
            raise CommandError(f"{error.message} {error.errors}") from error

        user.change_password_hash(password_hasher().hash(raw_password))
        user.unlock()
        repository.update(user)

        if options["reset_authenticator"]:
            # Through the authentication module's inbound port: this module never touches
            # another module's tables.
            from modules.authentication.infrastructure.dependencies import auth_use_cases

            auth_use_cases().reset_authenticator(user.id)

        DatabaseAuditLogger().log(
            AuditRecord(
                action=AuditAction.UPDATED,
                entity_type="User",
                entity_id=str(user.id),
                actor=None,
                actor_type=ActorType.SYSTEM,
                actor_label="reset_password",
                new_values={
                    "password": "changed",
                    "authenticator_reset": bool(options["reset_authenticator"]),
                },
                reason="Restablecimiento desde la línea de comandos",
            )
        )
        # Observer: the authentication module closes the account's open sessions.
        event_bus.publish(UserPasswordChanged(user_id=user.id, occurred_at=datetime.now(UTC)))

        self.stdout.write(self.style.SUCCESS(f"Contraseña restablecida: {user.email}"))
        if not options["password"]:
            self.stdout.write(f"Nueva contraseña (se muestra una sola vez): {raw_password}")
        if options["reset_authenticator"]:
            self.stdout.write("El autenticador se desvinculó: se pedirá un QR nuevo al ingresar.")
