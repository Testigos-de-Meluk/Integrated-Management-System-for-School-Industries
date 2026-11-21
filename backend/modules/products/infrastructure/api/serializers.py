"""DTOs of the Products REST API: they check shape and types; business rules live in the domain."""

from rest_framework import serializers

from modules.products.ports.inbound.product_use_cases import (
    CODE_MAX_LENGTH,
    NAME_MAX_LENGTH,
    PRODUCT_STATUSES,
    UNIT_MAX_LENGTH,
)
from modules.shared_kernel.infrastructure.api.pagination import PageQuerySerializer, page_serializer

STATUS_CHOICES = [(status, status) for status in PRODUCT_STATUSES]


class ProductSerializer(serializers.Serializer):
    """Output representation of a product: serializes a ``ProductView`` DTO."""

    id = serializers.UUIDField(read_only=True)
    code = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    unit_of_measure = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, read_only=True)
    is_selectable = serializers.BooleanField(read_only=True)


ProductPageSerializer = page_serializer("ProductPage", ProductSerializer)


class ProductQuerySerializer(PageQuerySerializer):
    code = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    unit_of_measure = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)


class ProductCreateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=CODE_MAX_LENGTH)
    name = serializers.CharField(max_length=NAME_MAX_LENGTH)
    unit_of_measure = serializers.CharField(max_length=UNIT_MAX_LENGTH)


class ProductUpdateSerializer(serializers.Serializer):
    """The code is not accepted: it cannot be modified once created (FR-02-03)."""

    name = serializers.CharField(max_length=NAME_MAX_LENGTH)
    unit_of_measure = serializers.CharField(max_length=UNIT_MAX_LENGTH)
