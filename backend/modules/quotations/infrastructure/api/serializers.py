"""DTOs of the quotation review REST API (Administrador)."""

from rest_framework import serializers

from modules.quotations.ports.inbound.quotation_review import (
    MAX_ITEMS,
    MAX_QUANTITY,
    QUOTATION_STATUSES,
    REASON_MAX_LENGTH,
    TERMS_MAX_LENGTH,
)
from modules.shared_kernel.infrastructure.api.pagination import PageQuerySerializer, page_serializer

STATUS_CHOICES = [(s, s) for s in QUOTATION_STATUSES]


def _money(**kwargs) -> serializers.DecimalField:
    """Whole Colombian pesos."""
    return serializers.DecimalField(
        max_digits=18, decimal_places=0, coerce_to_string=True, **kwargs
    )


# --- Input ------------------------------------------------------------------------------------


class QuotationQuerySerializer(PageQuerySerializer):
    issued_from = serializers.DateField(required=False)
    issued_to = serializers.DateField(required=False)
    contact = serializers.CharField(required=False, allow_blank=True, max_length=100)
    product = serializers.CharField(required=False, allow_blank=True, max_length=100)
    total_min = _money(required=False, min_value=0)
    total_max = _money(required=False, min_value=0)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)


class ReviewedItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(
        min_value=1,
        max_value=MAX_QUANTITY,
        error_messages={
            "min_value": "La cantidad debe ser mayor que cero.",
            "max_value": f"La cantidad máxima es {MAX_QUANTITY}.",
            "invalid": "La cantidad debe ser un número entero.",
        },
    )
    final_unit_price = _money(required=False, allow_null=True, default=None)


class ModifyQuotationSerializer(serializers.Serializer):
    items = ReviewedItemSerializer(
        many=True,
        allow_empty=False,
        max_length=MAX_ITEMS,
        error_messages={"empty": "La cotización debe tener al menos un producto."},
    )
    reason = serializers.CharField(max_length=REASON_MAX_LENGTH)
    commercial_terms = serializers.CharField(
        max_length=TERMS_MAX_LENGTH, required=False, allow_blank=True, default=""
    )
    dispatch_date = serializers.DateField(required=False, allow_null=True, default=None)


class ItemPriceSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    final_unit_price = _money(allow_null=True)


class ApproveQuotationSerializer(serializers.Serializer):
    prices = ItemPriceSerializer(many=True, max_length=MAX_ITEMS, required=False, default=list)
    dispatch_date = serializers.DateField(allow_null=True)
    commercial_terms = serializers.CharField(
        max_length=TERMS_MAX_LENGTH, required=False, allow_blank=True, default=""
    )


class RejectQuotationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=REASON_MAX_LENGTH)


class LinkCustomerSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField(allow_null=True)


# --- Output -----------------------------------------------------------------------------------


class QuotationSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.CharField()
    issued_at = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    requester_name = serializers.CharField()
    requester_email = serializers.CharField()
    requester_phone = serializers.CharField()
    requester_institution = serializers.CharField()
    products = serializers.ListField(child=serializers.CharField())
    total_min = serializers.CharField(allow_null=True)
    total_max = serializers.CharField(allow_null=True)
    final_total = serializers.CharField(allow_null=True)
    unpriced_items = serializers.IntegerField()
    has_customer = serializers.BooleanField()


QuotationPageSerializer = page_serializer("QuotationPage", QuotationSummarySerializer)


class ReviewItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    product_id = serializers.UUIDField()
    product_code = serializers.CharField()
    description = serializers.CharField()
    unit_of_measure = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price_min = serializers.CharField(allow_null=True)
    unit_price_max = serializers.CharField(allow_null=True)
    subtotal_min = serializers.CharField(allow_null=True)
    subtotal_max = serializers.CharField(allow_null=True)
    final_unit_price = serializers.CharField(allow_null=True)
    final_subtotal = serializers.CharField(allow_null=True)
    price_source = serializers.ChoiceField(
        choices=["HISTORY", "AI"],
        allow_null=True,
        help_text="HISTORY = this product's approved prices; AI = similar products",
    )


class LinkedCustomerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    tax_id = serializers.CharField()
    name = serializers.CharField()
    is_active = serializers.BooleanField()


class QuotationDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.CharField()
    issued_at = serializers.DateTimeField()
    valid_until = serializers.DateField()
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    is_editable = serializers.BooleanField()
    requester_name = serializers.CharField()
    requester_email = serializers.CharField()
    requester_phone = serializers.CharField()
    requester_institution = serializers.CharField()
    requester_tax_id = serializers.CharField()
    items = ReviewItemSerializer(many=True)
    total_min = serializers.CharField(allow_null=True)
    total_max = serializers.CharField(allow_null=True)
    final_total = serializers.CharField(allow_null=True)
    unpriced_items = serializers.IntegerField()
    estimated_dispatch_date = serializers.DateField(allow_null=True)
    dispatch_date_source = serializers.ChoiceField(choices=["SUGGESTED", "MANUAL"], allow_null=True)
    commercial_terms = serializers.CharField(allow_blank=True)
    rejection_reason = serializers.CharField(allow_blank=True)
    approved_at = serializers.DateTimeField(allow_null=True)
    approved_by_name = serializers.CharField(allow_blank=True)
    customer = LinkedCustomerSerializer(allow_null=True)
    suggested_customer = LinkedCustomerSerializer(allow_null=True)
    suggested_dispatch_date = serializers.DateField(allow_null=True)
