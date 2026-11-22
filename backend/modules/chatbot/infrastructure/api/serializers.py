"""DTOs of the public virtual assistant API (no account needed)."""

from rest_framework import serializers

from modules.shared_kernel.infrastructure.api.pagination import PageQuerySerializer, page_serializer


class CatalogItemSerializer(serializers.Serializer):
    """Public product data: never a price (RN-M2-01)."""

    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    unit_of_measure = serializers.CharField()


CatalogPageSerializer = page_serializer("PublicCatalogPage", CatalogItemSerializer)


class CatalogQuerySerializer(PageQuerySerializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=100)


class RequestedItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(
        min_value=1,
        max_value=100_000,
        error_messages={
            "min_value": "La cantidad debe ser mayor que cero.",
            "invalid": "La cantidad debe ser un número entero.",
        },
    )


class EstimateRequestSerializer(serializers.Serializer):
    items = RequestedItemSerializer(many=True, allow_empty=False, max_length=50)


class QuotationRequestSerializer(EstimateRequestSerializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.CharField(max_length=254)
    phone = serializers.CharField(max_length=30)
    institution = serializers.CharField(max_length=200, required=False, allow_blank=True)
    tax_id = serializers.CharField(max_length=20, required=False, allow_blank=True)
    data_consent = serializers.BooleanField()


class EstimatedItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_code = serializers.CharField()
    description = serializers.CharField()
    unit_of_measure = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price_min = serializers.CharField(
        allow_null=True, help_text="null = price to be confirmed"
    )
    unit_price_max = serializers.CharField(allow_null=True)
    subtotal_min = serializers.CharField(allow_null=True)
    subtotal_max = serializers.CharField(allow_null=True)
    price_source = serializers.ChoiceField(
        choices=["HISTORY", "AI"],
        allow_null=True,
        help_text="HISTORY = this product's approved prices; AI = similar products",
    )


class EstimateSerializer(serializers.Serializer):
    items = EstimatedItemSerializer(many=True)
    total_min = serializers.CharField(allow_null=True)
    total_max = serializers.CharField(allow_null=True)
    unpriced_items = serializers.IntegerField()


class PreliminaryQuotationSerializer(EstimateSerializer):
    id = serializers.UUIDField()
    number = serializers.CharField()
    issued_at = serializers.DateTimeField()
    valid_until = serializers.DateField()
    requester_name = serializers.CharField()
    requester_email = serializers.CharField()
    estimated_dispatch_date = serializers.DateField(allow_null=True)
    access_key = serializers.CharField(help_text="Required to download or email this quotation")


class AssistantOptionsSerializer(serializers.Serializer):
    free_text_enabled = serializers.BooleanField()


class ProposalRequestSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=1000)


class ProposedItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_code = serializers.CharField()
    description = serializers.CharField()
    unit_of_measure = serializers.CharField()
    quantity = serializers.IntegerField()


class ProposalSerializer(serializers.Serializer):
    items = ProposedItemSerializer(many=True)
    unavailable = serializers.ListField(child=serializers.CharField())


class AccessKeySerializer(serializers.Serializer):
    key = serializers.CharField(max_length=64)
