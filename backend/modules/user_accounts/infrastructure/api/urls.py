"""REST routes of the User Accounts module, mounted at /api/users/."""

from django.urls import path

from .views import (
    UserActivateView,
    UserDeactivateView,
    UserDetailView,
    UserListCreateView,
    UserPasswordView,
    UserUnlockView,
)

urlpatterns = [
    path("", UserListCreateView.as_view(), name="user-list"),
    path("<uuid:user_id>/", UserDetailView.as_view(), name="user-detail"),
    path("<uuid:user_id>/password/", UserPasswordView.as_view(), name="user-password"),
    path("<uuid:user_id>/activate/", UserActivateView.as_view(), name="user-activate"),
    path("<uuid:user_id>/deactivate/", UserDeactivateView.as_view(), name="user-deactivate"),
    path("<uuid:user_id>/unlock/", UserUnlockView.as_view(), name="user-unlock"),
]
