"""DTOs of the Odoo export queue API: shape and types only."""

from rest_framework import serializers

from modules.shared_kernel.infrastructure.api.pagination import PageQuerySerializer, page_serializer


class QueueItemSerializer(serializers.Serializer):
    product_code = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    unit_of_measure = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(read_only=True)


class QueueEntrySerializer(serializers.Serializer):
    work_order_id = serializers.UUIDField(read_only=True)
    number = serializers.CharField(read_only=True)
    quotation_number = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    enqueued_at = serializers.DateTimeField(read_only=True)
    customer_tax_id = serializers.CharField(read_only=True)
    customer_name = serializers.CharField(read_only=True)
    items = QueueItemSerializer(many=True, read_only=True)
    agreed_delivery_date = serializers.DateField(read_only=True)


QueuePageSerializer = page_serializer("ExportQueuePage", QueueEntrySerializer)


class QueueQuerySerializer(PageQuerySerializer):
    created_from = serializers.DateField(required=False)
    created_to = serializers.DateField(required=False)
    customer = serializers.CharField(required=False, allow_blank=True)
    number = serializers.CharField(required=False, allow_blank=True)


class ExportRequestSerializer(serializers.Serializer):
    work_order_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=True, max_length=500
    )


class BatchWorkOrderSerializer(serializers.Serializer):
    work_order_id = serializers.UUIDField(read_only=True)
    number = serializers.CharField(read_only=True)
    customer_name = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    cancelled_after_export = serializers.BooleanField(read_only=True)


class ExportBatchSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    file_name = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    created_by_name = serializers.CharField(read_only=True)
    work_orders = BatchWorkOrderSerializer(many=True, read_only=True)


BatchPageSerializer = page_serializer("ExportBatchPage", ExportBatchSerializer)
