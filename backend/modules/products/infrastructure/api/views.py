"""REST controllers (inbound adapters) of the Products module.

Each view only translates HTTP <-> use-case calls: it validates the DTO, resolves the actor,
calls the inbound port and serializes the result. No business rules here.
"""

from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.products.infrastructure.dependencies import product_use_cases
from modules.products.ports.inbound.product_use_cases import (
    ProductFilters,
    RegisterProductCommand,
    UpdateProductCommand,
)
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.infrastructure.api.actor import get_current_actor
from modules.shared_kernel.infrastructure.api.pagination import page_payload

from .serializers import (
    ProductCreateSerializer,
    ProductPageSerializer,
    ProductQuerySerializer,
    ProductSerializer,
    ProductUpdateSerializer,
)

TAG = ["products"]


class ProductListCreateView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="products_list",
        summary="List products (paginated, filterable)",
        parameters=[ProductQuerySerializer],
        responses=ProductPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = ProductQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        filters = ProductFilters(
            code=data.get("code") or None,
            name=data.get("name") or None,
            unit_of_measure=data.get("unit_of_measure") or None,
            status=data.get("status") or None,
        )
        page = product_use_cases().list_products(
            get_current_actor(request),
            filters,
            PageRequest(page=data["page"], size=data["page_size"]),
        )
        return Response(page_payload(page, ProductSerializer))

    @extend_schema(
        tags=TAG,
        summary="Register a product",
        request=ProductCreateSerializer,
        responses={201: ProductSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = ProductCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        product = product_use_cases().register_product(
            get_current_actor(request), RegisterProductCommand(**payload.validated_data)
        )
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductDetailView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="products_retrieve",
        summary="Get a product",
        responses=ProductSerializer,
    )
    def get(self, request: Request, product_id: UUID) -> Response:
        product = product_use_cases().get_product(get_current_actor(request), product_id)
        return Response(ProductSerializer(product).data)

    @extend_schema(
        tags=TAG,
        summary="Update name and unit of measure (the code is immutable)",
        request=ProductUpdateSerializer,
        responses=ProductSerializer,
    )
    def patch(self, request: Request, product_id: UUID) -> Response:
        payload = ProductUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        product = product_use_cases().update_product(
            get_current_actor(request), product_id, UpdateProductCommand(**payload.validated_data)
        )
        return Response(ProductSerializer(product).data)


class ProductActivateView(APIView):
    @extend_schema(
        tags=TAG, summary="Activate a product", request=None, responses=ProductSerializer
    )
    def post(self, request: Request, product_id: UUID) -> Response:
        product = product_use_cases().activate_product(get_current_actor(request), product_id)
        return Response(ProductSerializer(product).data)


class ProductDeactivateView(APIView):
    @extend_schema(
        tags=TAG, summary="Deactivate a product", request=None, responses=ProductSerializer
    )
    def post(self, request: Request, product_id: UUID) -> Response:
        product = product_use_cases().deactivate_product(get_current_actor(request), product_id)
        return Response(ProductSerializer(product).data)
