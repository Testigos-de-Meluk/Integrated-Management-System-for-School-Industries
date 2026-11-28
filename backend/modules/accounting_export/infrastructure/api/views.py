"""REST controllers of the Odoo export queue, mounted at /api/accounting-export/."""

from uuid import UUID

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.accounting_export.infrastructure.dependencies import export_queue
from modules.accounting_export.ports.inbound.export_queue import QueueFilters
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.infrastructure.api.actor import get_current_actor
from modules.shared_kernel.infrastructure.api.pagination import PageQuerySerializer, page_payload

from .serializers import (
    BatchPageSerializer,
    ExportBatchSerializer,
    ExportRequestSerializer,
    QueueEntrySerializer,
    QueuePageSerializer,
    QueueQuerySerializer,
)

TAG = ["accounting-export"]


class QueueView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="export_queue_list",
        summary="Work orders waiting to be exported to Odoo, oldest first (US 2.31 … US 2.33)",
        parameters=[QueueQuerySerializer],
        responses=QueuePageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = QueueQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        filters = QueueFilters(
            created_from=data.get("created_from"),
            created_to=data.get("created_to"),
            customer=data.get("customer") or None,
            number=data.get("number") or None,
        )
        page = export_queue().list_pending(
            get_current_actor(request),
            filters,
            PageRequest(page=data["page"], size=data["page_size"]),
        )
        return Response(page_payload(page, QueueEntrySerializer))


class BatchesView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="export_batches_list",
        summary="Exported batches, newest first, with the current status of each O.T.",
        parameters=[PageQuerySerializer],
        responses=BatchPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = PageQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        page = export_queue().list_batches(
            get_current_actor(request),
            PageRequest(page=query.validated_data["page"], size=query.validated_data["page_size"]),
        )
        return Response(page_payload(page, ExportBatchSerializer))

    @extend_schema(
        tags=TAG,
        operation_id="export_batches_create",
        summary="Generates the Odoo file of the selected O.T.s and registers them (US 2.34)",
        request=ExportRequestSerializer,
        responses={201: ExportBatchSerializer},
    )
    def post(self, request: Request) -> Response:
        body = ExportRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        batch = export_queue().export(
            get_current_actor(request), frozenset(body.validated_data["work_order_ids"])
        )
        return Response(ExportBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class BatchFileView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="export_batches_file",
        summary="Downloads the file of a batch again (importing it twice duplicates the orders)",
        responses={200: OpenApiResponse(OpenApiTypes.BINARY, description="Archivo .xlsx")},
    )
    def get(self, request: Request, batch_id: UUID) -> HttpResponse:
        file = export_queue().batch_file(get_current_actor(request), batch_id)
        response = HttpResponse(file.content, content_type=file.content_type)
        response["Content-Disposition"] = f'attachment; filename="{file.file_name}"'
        return response
