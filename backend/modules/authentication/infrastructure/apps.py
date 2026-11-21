from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    name = "modules.authentication.infrastructure"
    label = "authentication"
    verbose_name = "Authentication"

    def ready(self) -> None:
        """Subscribes to events of other modules (Observer pattern, NFR-05-01)."""
        from modules.authentication.domain.session import TerminationReason
        from modules.shared_kernel.infrastructure.events.in_process_event_bus import event_bus
        from modules.user_accounts.domain.events import UserDeactivated, UserPasswordChanged

        from .api import authentication  # noqa: F401  (registers the Swagger auth scheme)
        from .dependencies import auth_use_cases

        def close_sessions(reason: TerminationReason):
            return lambda event: auth_use_cases().terminate_sessions_for(event.user_id, reason)

        # FR-01-13: a deactivated account loses its active sessions immediately.
        event_bus.subscribe(UserDeactivated, close_sessions(TerminationReason.ACCOUNT_DEACTIVATED))
        event_bus.subscribe(UserPasswordChanged, close_sessions(TerminationReason.PASSWORD_CHANGED))
