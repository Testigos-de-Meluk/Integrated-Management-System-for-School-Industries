"""DTOs of the User Accounts REST API. The password hash is never part of any response."""

from rest_framework import serializers

from modules.shared_kernel.infrastructure.api.pagination import PageQuerySerializer, page_serializer
from modules.user_accounts.ports.inbound.user_account_use_cases import (
    ACCOUNT_STATUSES,
    EMAIL_MAX_LENGTH,
    FULL_NAME_MAX_LENGTH,
    JOB_TITLE_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    ROLES,
)

ROLE_CHOICES = [(role, role) for role in ROLES]
STATUS_CHOICES = [(status, status) for status in ACCOUNT_STATUSES]


class UserSerializer(serializers.Serializer):
    """Serializes a ``UserView`` DTO."""

    id = serializers.UUIDField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    job_title = serializers.CharField(read_only=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, read_only=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, read_only=True)
    last_access_at = serializers.DateTimeField(read_only=True, allow_null=True)
    is_locked = serializers.BooleanField(read_only=True)
    locked_until = serializers.DateTimeField(read_only=True, allow_null=True)


UserPageSerializer = page_serializer("UserPage", UserSerializer)


class UserQuerySerializer(PageQuerySerializer):
    name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)
    job_title = serializers.CharField(required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=ROLE_CHOICES, required=False)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)


class _PasswordFields(serializers.Serializer):
    password = serializers.CharField(
        required=False, allow_blank=True, max_length=PASSWORD_MAX_LENGTH, write_only=True
    )
    generate_password = serializers.BooleanField(required=False, default=False)


class UserCreateSerializer(_PasswordFields):
    full_name = serializers.CharField(max_length=FULL_NAME_MAX_LENGTH)
    email = serializers.CharField(max_length=EMAIL_MAX_LENGTH)  # format checked by the domain
    job_title = serializers.CharField(max_length=JOB_TITLE_MAX_LENGTH)
    role = serializers.ChoiceField(choices=ROLE_CHOICES)


class UserUpdateSerializer(serializers.Serializer):
    """The email is not accepted: it can never change (FR-01-12)."""

    full_name = serializers.CharField(max_length=FULL_NAME_MAX_LENGTH)
    job_title = serializers.CharField(max_length=JOB_TITLE_MAX_LENGTH)
    role = serializers.ChoiceField(choices=ROLE_CHOICES)


class ChangePasswordSerializer(_PasswordFields):
    pass
