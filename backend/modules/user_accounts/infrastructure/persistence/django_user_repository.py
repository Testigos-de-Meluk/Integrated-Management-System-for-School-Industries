from uuid import UUID

from django.db import IntegrityError, transaction

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.user_accounts.domain.exceptions import DuplicateEmail
from modules.user_accounts.domain.user import User
from modules.user_accounts.infrastructure.models import UserModel
from modules.user_accounts.ports.inbound.user_account_use_cases import UserFilters
from modules.user_accounts.ports.outbound.user_repository import UserRepository

from .mappers import apply_to_model, to_domain


class DjangoUserRepository(UserRepository):
    def get_by_id(self, user_id: UUID) -> User | None:
        model = UserModel.objects.filter(pk=user_id).first()
        return to_domain(model) if model else None

    def get_by_email(self, email: str) -> User | None:
        model = UserModel.objects.filter(email=email).first()
        return to_domain(model) if model else None

    def exists_with_email(self, email: str) -> bool:
        return UserModel.objects.filter(email=email).exists()

    def add(self, user: User) -> None:
        try:
            with transaction.atomic():
                apply_to_model(user, UserModel()).save(force_insert=True)
        except IntegrityError as error:
            raise DuplicateEmail() from error

    def update(self, user: User) -> None:
        model = UserModel.objects.get(pk=user.id)
        apply_to_model(user, model).save()

    def search(self, filters: UserFilters, page_request: PageRequest) -> Page[User]:
        queryset = UserModel.objects.all()
        if filters.name:
            queryset = queryset.filter(full_name__icontains=filters.name.strip())
        if filters.email:
            queryset = queryset.filter(email__icontains=filters.email.strip())
        if filters.job_title:
            queryset = queryset.filter(job_title__icontains=filters.job_title.strip())
        if filters.role:
            queryset = queryset.filter(role=filters.role)
        if filters.status:
            queryset = queryset.filter(status=filters.status)

        total = queryset.count()
        start = page_request.offset
        models = queryset.order_by("full_name", "email")[start : start + page_request.size]
        return Page([to_domain(m) for m in models], total, page_request)
