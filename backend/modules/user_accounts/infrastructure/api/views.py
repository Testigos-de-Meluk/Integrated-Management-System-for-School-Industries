"""REST controllers of the User Accounts module (Administrador and Superadministrador only)."""

from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.infrastructure.api.actor import get_current_actor
from modules.shared_kernel.infrastructure.api.pagination import page_payload
from modules.user_accounts.infrastructure.dependencies import user_account_use_cases
from modules.user_accounts.ports.inbound.user_account_use_cases import (
    ChangePasswordCommand,
    CreateUserCommand,
    UpdateUserCommand,
    UserFilters,
)

from .serializers import (
    ChangePasswordSerializer,
    UserCreateSerializer,
    UserPageSerializer,
    UserQuerySerializer,
    UserSerializer,
    UserUpdateSerializer,
)

TAG = ["users"]


def _respond(view, status_code: int = status.HTTP_200_OK) -> Response:
    return Response(UserSerializer(view).data, status=status_code)


class UserListCreateView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="users_list",
        summary="List user accounts (paginated, filterable)",
        parameters=[UserQuerySerializer],
        responses=UserPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = UserQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        filters = UserFilters(
            name=data.get("name") or None,
            email=data.get("email") or None,
            job_title=data.get("job_title") or None,
            role=data.get("role") or None,
            status=data.get("status") or None,
        )
        page = user_account_use_cases().list_users(
            get_current_actor(request),
            filters,
            PageRequest(page=data["page"], size=data["page_size"]),
        )
        return Response(page_payload(page, UserSerializer))

    @extend_schema(
        tags=TAG,
        summary="Create a user account and email its credentials",
        request=UserCreateSerializer,
        responses={201: UserSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = UserCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        view = user_account_use_cases().create_user(
            get_current_actor(request), CreateUserCommand(**payload.validated_data)
        )
        return _respond(view, status.HTTP_201_CREATED)


class UserDetailView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="users_retrieve",
        summary="Get a user account",
        responses=UserSerializer,
    )
    def get(self, request: Request, user_id: UUID) -> Response:
        return _respond(user_account_use_cases().get_user(get_current_actor(request), user_id))

    @extend_schema(
        tags=TAG,
        summary="Update name, job title and role (the email is immutable)",
        request=UserUpdateSerializer,
        responses=UserSerializer,
    )
    def patch(self, request: Request, user_id: UUID) -> Response:
        payload = UserUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        view = user_account_use_cases().update_user(
            get_current_actor(request), user_id, UpdateUserCommand(**payload.validated_data)
        )
        return _respond(view)


class UserPasswordView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Set a new password (manual or generated) and email it to the user",
        request=ChangePasswordSerializer,
        responses=UserSerializer,
    )
    def post(self, request: Request, user_id: UUID) -> Response:
        payload = ChangePasswordSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        view = user_account_use_cases().change_password(
            get_current_actor(request), user_id, ChangePasswordCommand(**payload.validated_data)
        )
        return _respond(view)


class UserActivateView(APIView):
    @extend_schema(
        tags=TAG, summary="Reactivate an account", request=None, responses=UserSerializer
    )
    def post(self, request: Request, user_id: UUID) -> Response:
        return _respond(user_account_use_cases().activate_user(get_current_actor(request), user_id))


class UserDeactivateView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Deactivate an account and close its sessions",
        request=None,
        responses=UserSerializer,
    )
    def post(self, request: Request, user_id: UUID) -> Response:
        return _respond(
            user_account_use_cases().deactivate_user(get_current_actor(request), user_id)
        )


class UserUnlockView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Unlock an account locked by failed logins",
        request=None,
        responses=UserSerializer,
    )
    def post(self, request: Request, user_id: UUID) -> Response:
        return _respond(user_account_use_cases().unlock_user(get_current_actor(request), user_id))
