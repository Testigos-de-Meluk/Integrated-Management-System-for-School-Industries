"""PostgreSQL implementation of the ``ProductRepository`` port, using the Django ORM."""

from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from modules.products.domain.exceptions import DuplicateProductCode
from modules.products.domain.product import Product
from modules.products.infrastructure.models import ProductModel
from modules.products.ports.inbound.product_use_cases import ProductFilters
from modules.products.ports.outbound.product_repository import ProductRepository
from modules.shared_kernel.domain.pagination import Page, PageRequest

from .mappers import apply_to_model, to_domain


class DjangoProductRepository(ProductRepository):
    def get_by_id(self, product_id: UUID) -> Product | None:
        model = ProductModel.objects.filter(pk=product_id).first()
        return to_domain(model) if model else None

    def exists_with_code(self, code: str) -> bool:
        return ProductModel.objects.filter(code=code).exists()

    def add(self, product: Product) -> None:
        try:
            # Savepoint: a duplicate code must not break an outer transaction.
            with transaction.atomic():
                apply_to_model(product, ProductModel()).save(force_insert=True)
        except IntegrityError as error:
            # Two users registering the same code at the same time: the unique index wins.
            raise DuplicateProductCode() from error

    def update(self, product: Product) -> None:
        model = ProductModel.objects.get(pk=product.id)
        apply_to_model(product, model).save(
            update_fields=["name", "unit_of_measure", "status", "updated_at"]
        )

    def search(self, filters: ProductFilters, page_request: PageRequest) -> Page[Product]:
        queryset = ProductModel.objects.all()
        if filters.code:
            queryset = queryset.filter(code__icontains=filters.code.strip())
        if filters.name:
            queryset = queryset.filter(name__icontains=filters.name.strip())
        if filters.unit_of_measure:
            queryset = queryset.filter(unit_of_measure__iexact=filters.unit_of_measure.strip())
        if filters.status:
            queryset = queryset.filter(status=filters.status)
        if filters.text:
            term = filters.text.strip()
            queryset = queryset.filter(Q(code__icontains=term) | Q(name__icontains=term))

        total = queryset.count()
        start = page_request.offset
        models = queryset.order_by("code")[start : start + page_request.size]
        return Page(items=[to_domain(m) for m in models], total=total, request=page_request)
