from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Server-side pagination for every listing endpoint (NFR-07-02: max 50 records per page)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50
