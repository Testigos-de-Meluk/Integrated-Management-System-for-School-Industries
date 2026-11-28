"""REST controllers of the Siigo export queue, mounted at /api/accounting-export/."""

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.accounting_export.infrastructure.dependencies import export_queue
from modules.accounting_export.ports.inbound.export_queue import QueueFilters
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.infrastructure.api.actor import get_current_actor
from modules.shared_kernel.infrastructure.api.pagination import page_payload

from .serializers import QueueEntrySerializer, QueuePageSerializer, QueueQuerySerializer

TAG = ["accounting-export"]


class QueueView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="export_queue_list",
        summary="Work orders waiting to be exported to Siigo, oldest first (US 2.31 … US 2.33)",
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
