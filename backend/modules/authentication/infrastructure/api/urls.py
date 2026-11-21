"""REST routes of the Authentication module, mounted at /api/auth/."""

from django.urls import path

from .views import (
    ActivityView,
    EnrollmentConfirmView,
    EnrollmentStartView,
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    VerifyCodeView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("enrollment/", EnrollmentStartView.as_view(), name="auth-enrollment"),
    path("enrollment/confirm/", EnrollmentConfirmView.as_view(), name="auth-enrollment-confirm"),
    path("verify/", VerifyCodeView.as_view(), name="auth-verify"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("activity/", ActivityView.as_view(), name="auth-activity"),
]
