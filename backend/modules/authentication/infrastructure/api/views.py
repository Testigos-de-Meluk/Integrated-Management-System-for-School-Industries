"""REST controllers of the Authentication module.

The refresh token travels only in an ``httpOnly`` cookie (JavaScript cannot read it), restricted to
``/api/auth/`` and ``SameSite=Strict``. The access token is returned in the body and the frontend
keeps it in memory.
"""

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.authentication.infrastructure.dependencies import auth_use_cases
from modules.authentication.ports.inbound.auth_use_cases import SessionTokens
from modules.shared_kernel.infrastructure.api.actor import client_ip, get_current_actor
from modules.shared_kernel.infrastructure.api.exceptions import error_response

from .serializers import (
    CodeSerializer,
    CurrentUserSerializer,
    EnrollmentSerializer,
    LoginChallengeSerializer,
    LoginSerializer,
    PreAuthSerializer,
    SessionSerializer,
)

TAG = ["auth"]
REFRESH_COOKIE = "imsi_refresh"
COOKIE_PATH = "/api/auth/"
REFRESH_CONFLICT = "REFRESH_CONFLICT"  # error code of a lost refresh race (409)
ERROR = OpenApiResponse(description='{"detail", "errors", "code"}')


def _session_response(tokens: SessionTokens) -> Response:
    response = Response(SessionSerializer(tokens).data)
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        expires=tokens.refresh_expires_at,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Strict",
    )
    return response


def _clear_cookie(response: Response) -> Response:
    response.delete_cookie(REFRESH_COOKIE, path=COOKIE_PATH, samesite="Strict")
    return response


class PublicAuthView(APIView):
    """Endpoints used before having an access token: no authentication is attempted."""

    authentication_classes: list = []
    permission_classes: list = []


class LoginView(PublicAuthView):
    throttle_scope = "auth_login"  # audit F-04: per IP

    @extend_schema(
        tags=TAG,
        summary="Step 1: email + password → pre-authentication token",
        request=LoginSerializer,
        responses={200: LoginChallengeSerializer, 401: ERROR, 429: ERROR},
    )
    def post(self, request: Request) -> Response:
        payload = LoginSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        outcome = auth_use_cases().login(
            payload.validated_data["email"], payload.validated_data["password"], client_ip(request)
        )
        if outcome.error:
            return error_response(outcome.error)  # not raised: the failed attempt must be saved
        return Response(LoginChallengeSerializer(outcome.value).data)


class EnrollmentStartView(PublicAuthView):
    throttle_scope = "auth_code"

    @extend_schema(
        tags=TAG,
        summary="Step 2 (first login): QR code and secret to link the authenticator app",
        request=PreAuthSerializer,
        responses={200: EnrollmentSerializer, 401: ERROR, 409: ERROR},
    )
    def post(self, request: Request) -> Response:
        payload = PreAuthSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        view = auth_use_cases().start_enrollment(payload.validated_data["pre_auth_token"])
        return Response(EnrollmentSerializer(view).data)


class EnrollmentConfirmView(PublicAuthView):
    throttle_scope = "auth_code"

    @extend_schema(
        tags=TAG,
        summary="Step 3 (first login): confirm the link with a code and open the session",
        request=CodeSerializer,
        responses={200: SessionSerializer, 401: ERROR, 409: ERROR},
    )
    def post(self, request: Request) -> Response:
        payload = CodeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        tokens = auth_use_cases().confirm_enrollment(
            payload.validated_data["pre_auth_token"],
            payload.validated_data["code"],
            client_ip(request),
        )
        if tokens.error:
            return error_response(tokens.error)
        return _session_response(tokens.value)


class VerifyCodeView(PublicAuthView):
    throttle_scope = "auth_code"

    @extend_schema(
        tags=TAG,
        summary="Step 2: 6-digit code from the authenticator app → session",
        request=CodeSerializer,
        responses={200: SessionSerializer, 401: ERROR},
    )
    def post(self, request: Request) -> Response:
        payload = CodeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        outcome = auth_use_cases().verify_code(
            payload.validated_data["pre_auth_token"],
            payload.validated_data["code"],
            client_ip(request),
        )
        if outcome.error:
            return error_response(outcome.error)
        return _session_response(outcome.value)


class RefreshView(PublicAuthView):
    throttle_scope = "auth_refresh"

    @extend_schema(
        tags=TAG,
        summary="New access token using the refresh cookie (does not count as activity)",
        request=None,
        responses={200: SessionSerializer, 401: ERROR, 409: ERROR},
    )
    def post(self, request: Request) -> Response:
        outcome = auth_use_cases().refresh(request.COOKIES.get(REFRESH_COOKIE, ""))
        if outcome.error and outcome.error.code == REFRESH_CONFLICT:
            # Another tab won the rotation: the cookie is shared by every tab, so erasing it here
            # would also log out the winner. The session is still open; the client retries.
            return error_response(outcome.error)
        if outcome.error:
            return _clear_cookie(error_response(outcome.error))
        return _session_response(outcome.value)


class LogoutView(APIView):
    @extend_schema(
        tags=TAG, summary="Close the current session", request=None, responses={204: None}
    )
    def post(self, request: Request) -> Response:
        auth_use_cases().logout(get_current_actor(request))
        return _clear_cookie(Response(status=status.HTTP_204_NO_CONTENT))


class MeView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Current user and permissions",
        responses={200: CurrentUserSerializer, 401: ERROR},
    )
    def get(self, request: Request) -> Response:
        user = auth_use_cases().current_user(get_current_actor(request))
        return Response(CurrentUserSerializer(user).data)


class ActivityView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Report user activity (clicks/scroll) to keep the session alive",
        request=None,
        responses={204: None, 401: ERROR},
    )
    def post(self, request: Request) -> Response:
        get_current_actor(request)  # authenticating the request already records the activity
        return Response(status=status.HTTP_204_NO_CONTENT)
