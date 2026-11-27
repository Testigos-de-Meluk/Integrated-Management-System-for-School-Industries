"""REST controllers (inbound adapters) of the Work Orders module, mounted at /api/work-orders/.

Each view only translates HTTP <-> use-case calls. State changes are POST actions.
"""

from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.infrastructure.api.actor import get_current_actor
from modules.shared_kernel.infrastructure.api.pagination import page_payload
from modules.work_orders.infrastructure.dependencies import work_order_management
from modules.work_orders.ports.inbound.work_order_management import (
    GenerateWorkOrderCommand,
    UpdateWorkOrderCommand,
    WorkOrderFilters,
    WorkOrderItemInput,
)

from .serializers import (
    AvailableQuotationPageSerializer,
    AvailableQuotationQuerySerializer,
    AvailableQuotationSerializer,
    CancelWorkOrderSerializer,
    GenerateWorkOrderSerializer,
    ReconcileWorkOrderSerializer,
    UpdateWorkOrderSerializer,
    WorkOrderDetailSerializer,
    WorkOrderPageSerializer,
    WorkOrderQuerySerializer,
    WorkOrderSummarySerializer,
)

TAG = ["work-orders"]


class WorkOrderListCreateView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="work_orders_list",
        summary="List work orders (paginated, filterable, US 2.35 / US 2.36)",
        parameters=[WorkOrderQuerySerializer],
        responses=WorkOrderPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = WorkOrderQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        filters = WorkOrderFilters(
            number=data.get("number") or None,
            quotation_number=data.get("quotation_number") or None,
            customer=data.get("customer") or None,
            product=data.get("product") or None,
            agreed_from=data.get("agreed_from"),
            agreed_to=data.get("agreed_to"),
            status=data.get("status") or None,
        )
        page = work_order_management().list_work_orders(
            get_current_actor(request),
            filters,
            PageRequest(page=data["page"], size=data["page_size"]),
        )
        return Response(page_payload(page, WorkOrderSummarySerializer))

    @extend_schema(
        tags=TAG,
        summary="Generate a work order from an approved quotation (US 2.37)",
        request=GenerateWorkOrderSerializer,
        responses={201: WorkOrderDetailSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = GenerateWorkOrderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = work_order_management().generate(
            get_current_actor(request), GenerateWorkOrderCommand(**payload.validated_data)
        )
        return Response(WorkOrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)


class AvailableQuotationsView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Approved quotations without an active work order",
        parameters=[AvailableQuotationQuerySerializer],
        responses=AvailableQuotationPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = AvailableQuotationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        page = work_order_management().available_quotations(
            get_current_actor(request),
            data.get("search") or None,
            PageRequest(page=data["page"], size=data["page_size"]),
        )
        return Response(page_payload(page, AvailableQuotationSerializer))


class WorkOrderDetailView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="work_orders_retrieve",
        summary="Get a work order",
        responses=WorkOrderDetailSerializer,
    )
    def get(self, request: Request, work_order_id: UUID) -> Response:
        order = work_order_management().get_work_order(get_current_actor(request), work_order_id)
        return Response(WorkOrderDetailSerializer(order).data)

    @extend_schema(
        tags=TAG,
        summary="Edit customer, items and agreed date (only while Pendiente, US 2.38)",
        request=UpdateWorkOrderSerializer,
        responses=WorkOrderDetailSerializer,
    )
    def patch(self, request: Request, work_order_id: UUID) -> Response:
        payload = UpdateWorkOrderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        command = UpdateWorkOrderCommand(
            customer_id=data["customer_id"],
            items=tuple(WorkOrderItemInput(i["product_id"], i["quantity"]) for i in data["items"]),
            agreed_delivery_date=data["agreed_delivery_date"],
        )
        order = work_order_management().update(get_current_actor(request), work_order_id, command)
        return Response(WorkOrderDetailSerializer(order).data)


class WorkOrderCancelView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Annul a work order with a reason (US 2.39)",
        request=CancelWorkOrderSerializer,
        responses=WorkOrderDetailSerializer,
    )
    def post(self, request: Request, work_order_id: UUID) -> Response:
        payload = CancelWorkOrderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = work_order_management().cancel(
            get_current_actor(request), work_order_id, payload.validated_data["reason"]
        )
        return Response(WorkOrderDetailSerializer(order).data)


class WorkOrderReconcileView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Registrada en Siigo → Conciliada with the real dispatch date (US 2.40)",
        request=ReconcileWorkOrderSerializer,
        responses=WorkOrderDetailSerializer,
    )
    def post(self, request: Request, work_order_id: UUID) -> Response:
        payload = ReconcileWorkOrderSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        order = work_order_management().reconcile(
            get_current_actor(request),
            work_order_id,
            payload.validated_data["actual_dispatch_date"],
        )
        return Response(WorkOrderDetailSerializer(order).data)
