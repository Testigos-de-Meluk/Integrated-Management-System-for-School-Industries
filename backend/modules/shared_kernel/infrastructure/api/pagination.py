"""Server-side pagination for every listing endpoint (NFR-07-02: max 50 records per page)."""

from typing import Any

from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination

from modules.shared_kernel.domain.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page


class StandardPagination(PageNumberPagination):
    """DRF paginator with the same limits, for views that paginate Django querysets directly."""

    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE


class PageQuerySerializer(serializers.Serializer):
    """Common ``page`` / ``page_size`` query parameters. Listing filters extend it."""

    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_PAGE_SIZE, default=DEFAULT_PAGE_SIZE
    )


def page_payload(page: Page, item_serializer: type[serializers.Serializer]) -> dict[str, Any]:
    """Serializes a domain :class:`Page` with the standard listing envelope."""
    return {
        "count": page.total,
        "page": page.request.page,
        "page_size": page.request.size,
        "total_pages": page.total_pages,
        "results": item_serializer(page.items, many=True).data,
    }


def page_serializer(name: str, item_serializer: type[serializers.Serializer]) -> type:
    """Builds the OpenAPI component that documents a paginated response."""
    return type(
        name,
        (serializers.Serializer,),
        {
            "count": serializers.IntegerField(),
            "page": serializers.IntegerField(),
            "page_size": serializers.IntegerField(),
            "total_pages": serializers.IntegerField(),
            "results": item_serializer(many=True),
        },
    )
