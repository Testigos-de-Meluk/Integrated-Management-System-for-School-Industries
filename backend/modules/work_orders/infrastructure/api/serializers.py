"""DTOs of the Work Orders REST API: shape and types only; business rules live in the domain."""

from rest_framework import serializers

from modules.shared_kernel.infrastructure.api.pagination import PageQuerySerializer, page_serializer
from modules.work_orders.ports.inbound.work_order_management import (
    MAX_ITEMS,
    MAX_QUANTITY,
    REASON_MAX_LENGTH,
    WORK_ORDER_STATUSES,
)

STATUS_CHOICES = [(status, status) for status in WORK_ORDER_STATUSES]


class WorkOrderItemSerializer(serializers.Serializer):
    product_id = serializers.UUIDField(read_only=True)
    product_code = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    unit_of_measure = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(read_only=True)


class WorkOrderSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    number = serializers.CharField(read_only=True)
    quotation_id = serializers.UUIDField(read_only=True)
    quotation_number = serializers.CharField(read_only=True)
    customer_id = serializers.UUIDField(read_only=True)
    customer_tax_id = serializers.CharField(read_only=True)
    customer_name = serializers.CharField(read_only=True)
    items = WorkOrderItemSerializer(many=True, read_only=True)
    agreed_delivery_date = serializers.DateField(read_only=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class WorkOrderDetailSerializer(WorkOrderSummarySerializer):
    actual_dispatch_date = serializers.DateField(read_only=True, allow_null=True)
    cancellation_reason = serializers.CharField(read_only=True)
    created_by_name = serializers.CharField(read_only=True)
    can_edit = serializers.BooleanField(read_only=True)
    can_reconcile = serializers.BooleanField(read_only=True)
    can_cancel = serializers.BooleanField(read_only=True)
    was_exported = serializers.BooleanField(read_only=True)


WorkOrderPageSerializer = page_serializer("WorkOrderPage", WorkOrderSummarySerializer)


class AvailableQuotationSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    number = serializers.CharField(read_only=True)
    approved_at = serializers.DateTimeField(read_only=True)
    requester_name = serializers.CharField(read_only=True)
    requester_institution = serializers.CharField(read_only=True)
    requester_tax_id = serializers.CharField(read_only=True)
    customer_id = serializers.UUIDField(read_only=True, allow_null=True)
    customer_name = serializers.CharField(read_only=True, allow_null=True)
    customer_active = serializers.BooleanField(read_only=True, allow_null=True)
    dispatch_date = serializers.DateField(read_only=True, allow_null=True)
    items = WorkOrderItemSerializer(many=True, read_only=True)


AvailableQuotationPageSerializer = page_serializer(
    "AvailableQuotationPage", AvailableQuotationSerializer
)


class WorkOrderQuerySerializer(PageQuerySerializer):
    number = serializers.CharField(required=False, allow_blank=True)
    quotation_number = serializers.CharField(required=False, allow_blank=True)
    customer = serializers.CharField(required=False, allow_blank=True)
    product = serializers.CharField(required=False, allow_blank=True)
    agreed_from = serializers.DateField(required=False)
    agreed_to = serializers.DateField(required=False)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)


class AvailableQuotationQuerySerializer(PageQuerySerializer):
    search = serializers.CharField(required=False, allow_blank=True)


class GenerateWorkOrderSerializer(serializers.Serializer):
    quotation_id = serializers.UUIDField()
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    agreed_delivery_date = serializers.DateField(required=False, allow_null=True)


class WorkOrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY)


class UpdateWorkOrderSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    items = WorkOrderItemInputSerializer(many=True, min_length=1, max_length=MAX_ITEMS)
    agreed_delivery_date = serializers.DateField()


class CancelWorkOrderSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=REASON_MAX_LENGTH)


class ReconcileWorkOrderSerializer(serializers.Serializer):
    actual_dispatch_date = serializers.DateField()
