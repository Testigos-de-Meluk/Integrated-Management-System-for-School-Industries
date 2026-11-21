from modules.shared_kernel.domain.security import RoleType
from modules.user_accounts.domain.user import AccountStatus, User
from modules.user_accounts.infrastructure.models import UserModel

_FIELDS = (
    "full_name",
    "email",
    "job_title",
    "password_hash",
    "last_access_at",
    "failed_login_attempts",
    "last_failed_login_at",
    "locked_until",
)


def to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        role=RoleType(model.role),
        status=AccountStatus(model.status),
        **{name: getattr(model, name) for name in _FIELDS},
    )


def apply_to_model(user: User, model: UserModel) -> UserModel:
    model.id = user.id
    model.role = user.role.value
    model.status = user.status.value
    for name in _FIELDS:
        setattr(model, name, getattr(user, name))
    return model
