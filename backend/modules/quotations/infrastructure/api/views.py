"""REST controllers of the quotation review (Administrador, Superadministrador)."""

from uuid import UUID

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.quotations.infrastructure.dependencies import quotation_review
from modules.quotations.ports.inbound.quotation_review import (
    ApproveQuotationCommand,
    ItemPrice,
    ModifyQuotationCommand,
    QuotationFilters,
    ReviewedItem,
)
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.infrastructure.api.actor import get_current_actor
from modules.shared_kernel.infrastructure.api.pagination import page_payload

from .serializers import (
    ApproveQuotationSerializer,
    LinkCustomerSerializer,
    ModifyQuotationSerializer,
    QuotationDetailSerializer,
    QuotationPageSerializer,
    QuotationQuerySerializer,
    QuotationSummarySerializer,
    RejectQuotationSerializer,
)

TAG = ["quotations"]


def _detail(view) -> Response:
    return Response(QuotationDetailSerializer(view).data)


class QuotationListView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="quotations_list",
        summary="Review tray: quotations, newest first (paginated, filterable)",
        parameters=[QuotationQuerySerializer],
        responses=QuotationPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = QuotationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        filters = QuotationFilters(
            issued_from=data.get("issued_from"),
            issued_to=data.get("issued_to"),
            contact=data.get("contact") or None,
            product=data.get("product") or None,
            total_min=data.get("total_min"),
            total_max=data.get("total_max"),
            status=data.get("status") or None,
        )
        page = quotation_review().list_quotations(
            get_current_actor(request),
            filters,
            PageRequest(page=data["page"], size=data["page_size"]),
        )
        return Response(page_payload(page, QuotationSummarySerializer))


class QuotationDetailView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="quotations_retrieve",
        summary="Get a quotation with its items",
        responses=QuotationDetailSerializer,
    )
    def get(self, request: Request, quotation_id: UUID) -> Response:
        return _detail(quotation_review().get_quotation(get_current_actor(request), quotation_id))


class QuotationModifyView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Modify items, final prices, terms or dispatch date (→ Modificada)",
        request=ModifyQuotationSerializer,
        responses=QuotationDetailSerializer,
    )
    def post(self, request: Request, quotation_id: UUID) -> Response:
        payload = ModifyQuotationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        command = ModifyQuotationCommand(
            items=tuple(
                ReviewedItem(i["product_id"], i["quantity"], i.get("final_unit_price"))
                for i in data["items"]
            ),
            reason=data["reason"],
            commercial_terms=data["commercial_terms"],
            dispatch_date=data["dispatch_date"],
        )
        view = quotation_review().modify_quotation(
            get_current_actor(request), quotation_id, command
        )
        return _detail(view)


class QuotationApproveView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Approve with final unit prices and dispatch date (→ Aprobada, emails the PDF)",
        request=ApproveQuotationSerializer,
        responses=QuotationDetailSerializer,
    )
    def post(self, request: Request, quotation_id: UUID) -> Response:
        payload = ApproveQuotationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        command = ApproveQuotationCommand(
            prices=tuple(ItemPrice(p["item_id"], p["final_unit_price"]) for p in data["prices"]),
            dispatch_date=data["dispatch_date"],
            commercial_terms=data["commercial_terms"],
        )
        view = quotation_review().approve_quotation(
            get_current_actor(request), quotation_id, command
        )
        return _detail(view)


class QuotationRejectView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Reject with a reason (→ Rechazada, emails the requester)",
        request=RejectQuotationSerializer,
        responses=QuotationDetailSerializer,
    )
    def post(self, request: Request, quotation_id: UUID) -> Response:
        payload = RejectQuotationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        view = quotation_review().reject_quotation(
            get_current_actor(request), quotation_id, payload.validated_data["reason"]
        )
        return _detail(view)


class QuotationCustomerView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Link a registered active customer (null unlinks it while in review)",
        request=LinkCustomerSerializer,
        responses=QuotationDetailSerializer,
    )
    def post(self, request: Request, quotation_id: UUID) -> Response:
        payload = LinkCustomerSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        view = quotation_review().link_customer(
            get_current_actor(request), quotation_id, payload.validated_data["customer_id"]
        )
        return _detail(view)


class QuotationPdfView(APIView):
    @extend_schema(
        tags=TAG,
        summary="PDF: formal once approved, preliminary before",
        responses={(200, "application/pdf"): OpenApiResponse(description="PDF file")},
    )
    def get(self, request: Request, quotation_id: UUID) -> HttpResponse:
        document = quotation_review().document(get_current_actor(request), quotation_id)
        response = HttpResponse(document.content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{document.filename}"'
        return response
