"""Public REST controllers of the virtual assistant (Chatbot Controllers in the architecture).

These endpoints are open to the internet: no authentication, and every one has a rate limit per
IP address (``throttle_scope``). They only reach the system through inbound ports: the products
catalog (``ProductCatalog``) and the quotation requests (``QuotationRequests``).
"""

from uuid import UUID

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.products.infrastructure.dependencies import product_catalog
from modules.quotations.infrastructure.dependencies import quotation_requests
from modules.quotations.ports.inbound.quotation_requests import (
    RequestedItem,
    RequestQuotationCommand,
)
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.infrastructure.api.actor import client_ip
from modules.shared_kernel.infrastructure.api.pagination import page_payload

from .serializers import (
    AccessKeySerializer,
    AssistantOptionsSerializer,
    CatalogItemSerializer,
    CatalogPageSerializer,
    CatalogQuerySerializer,
    EstimateRequestSerializer,
    EstimateSerializer,
    PreliminaryQuotationSerializer,
    ProposalRequestSerializer,
    ProposalSerializer,
    QuotationRequestSerializer,
)

TAG = ["public assistant"]


class PublicView(APIView):
    authentication_classes: list = []
    permission_classes: list = []


def _items(data) -> tuple[RequestedItem, ...]:
    return tuple(RequestedItem(i["product_id"], i["quantity"]) for i in data["items"])


class PublicCatalogView(PublicView):
    throttle_scope = "public_catalog"

    @extend_schema(
        tags=TAG,
        summary="Active products to choose from (no prices)",
        parameters=[CatalogQuerySerializer],
        responses=CatalogPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = CatalogQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        page = product_catalog().search_selectable(
            data.get("search"), PageRequest(page=data["page"], size=data["page_size"])
        )
        return Response(page_payload(page, CatalogItemSerializer))


class AssistantOptionsView(PublicView):
    throttle_scope = "public_catalog"

    @extend_schema(
        tags=TAG,
        summary="Which optional assistant features are available (AI free text)",
        responses=AssistantOptionsSerializer,
    )
    def get(self, request: Request) -> Response:
        return Response(AssistantOptionsSerializer(quotation_requests().assistant_options()).data)


class ProposalView(PublicView):
    throttle_scope = "public_proposal"

    @extend_schema(
        tags=TAG,
        summary="Describe your needs in free text; the AI proposes catalog products (not stored)",
        request=ProposalRequestSerializer,
        responses={200: ProposalSerializer, 503: OpenApiResponse(description="AI unavailable")},
    )
    def post(self, request: Request) -> Response:
        payload = ProposalRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        proposal = quotation_requests().propose_items(payload.validated_data["description"])
        return Response(ProposalSerializer(proposal).data)


class EstimateView(PublicView):
    throttle_scope = "public_estimate"

    @extend_schema(
        tags=TAG,
        summary="Live price-range estimate of the selection (nothing is saved)",
        request=EstimateRequestSerializer,
        responses=EstimateSerializer,
    )
    def post(self, request: Request) -> Response:
        payload = EstimateRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        estimate = quotation_requests().estimate(_items(payload.validated_data))
        return Response(EstimateSerializer(estimate).data)


class QuotationRequestView(PublicView):
    throttle_scope = "public_quotation"

    @extend_schema(
        tags=TAG,
        summary="Request a preliminary quotation (saved as 'Pendiente de revisión')",
        request=QuotationRequestSerializer,
        responses={201: PreliminaryQuotationSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = QuotationRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        command = RequestQuotationCommand(
            full_name=data["full_name"],
            email=data["email"],
            phone=data["phone"],
            institution=data.get("institution"),
            tax_id=data.get("tax_id"),
            items=_items(data),
            data_consent=data["data_consent"],
        )
        quotation = quotation_requests().request_quotation(command, client_ip(request))
        return Response(
            PreliminaryQuotationSerializer(quotation).data, status=status.HTTP_201_CREATED
        )


class QuotationPdfView(PublicView):
    throttle_scope = "public_document"

    @extend_schema(
        tags=TAG,
        summary="Download the preliminary quotation as PDF",
        parameters=[OpenApiParameter("key", str, required=True)],
        responses={(200, "application/pdf"): OpenApiResponse(description="PDF file")},
    )
    def get(self, request: Request, quotation_id: UUID) -> HttpResponse:
        query = AccessKeySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        document = quotation_requests().document(quotation_id, query.validated_data["key"])
        response = HttpResponse(document.content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{document.filename}"'
        return response


class QuotationEmailView(PublicView):
    throttle_scope = "public_document"

    @extend_schema(
        tags=TAG,
        summary="Email the preliminary quotation PDF to the requester",
        request=AccessKeySerializer,
        responses={202: OpenApiResponse(description='{"sent_to": "<email>"}')},
    )
    def post(self, request: Request, quotation_id: UUID) -> Response:
        payload = AccessKeySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        sent_to = quotation_requests().email_document(quotation_id, payload.validated_data["key"])
        return Response({"sent_to": sent_to}, status=status.HTTP_202_ACCEPTED)
