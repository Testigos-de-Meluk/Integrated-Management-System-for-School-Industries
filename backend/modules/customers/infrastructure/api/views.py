"""REST controllers of the Customers module (Operador, Administrador, Superadministrador)."""

from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.customers.infrastructure.dependencies import customer_use_cases
from modules.customers.ports.inbound.customer_use_cases import (
    CustomerFilters,
    RegisterCustomerCommand,
    UpdateCustomerCommand,
)
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.infrastructure.api.actor import get_current_actor
from modules.shared_kernel.infrastructure.api.pagination import (
    PageQuerySerializer,
    page_payload,
)

from .serializers import (
    CustomerCreateSerializer,
    CustomerPageSerializer,
    CustomerQuerySerializer,
    CustomerSerializer,
    CustomerUpdateSerializer,
    HistoryEntrySerializer,
    HistoryPageSerializer,
    NoteInputSerializer,
    NotePageSerializer,
    NoteSerializer,
)

TAG = ["customers"]


def _page_request(request: Request) -> PageRequest:
    query = PageQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return PageRequest(page=query.validated_data["page"], size=query.validated_data["page_size"])


def _customer(view, status_code=status.HTTP_200_OK) -> Response:
    return Response(CustomerSerializer(view).data, status=status_code)


class CustomerListCreateView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="customers_list",
        summary="List customers (paginated, filterable)",
        parameters=[CustomerQuerySerializer],
        responses=CustomerPageSerializer,
    )
    def get(self, request: Request) -> Response:
        query = CustomerQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        filters = CustomerFilters(
            tax_id=data.get("tax_id") or None,
            name=data.get("name") or None,
            commercial_contact=data.get("commercial_contact") or None,
            status=data.get("status") or None,
        )
        page = customer_use_cases().list_customers(
            get_current_actor(request),
            filters,
            PageRequest(page=data["page"], size=data["page_size"]),
        )
        return Response(page_payload(page, CustomerSerializer))

    @extend_schema(
        tags=TAG,
        summary="Register a customer (natural person or legal entity)",
        request=CustomerCreateSerializer,
        responses={201: CustomerSerializer},
    )
    def post(self, request: Request) -> Response:
        payload = CustomerCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        view = customer_use_cases().register_customer(
            get_current_actor(request), RegisterCustomerCommand(**payload.validated_data)
        )
        return _customer(view, status.HTTP_201_CREATED)


class CustomerDetailView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="customers_retrieve",
        summary="Get a customer",
        responses=CustomerSerializer,
    )
    def get(self, request: Request, customer_id: UUID) -> Response:
        return _customer(customer_use_cases().get_customer(get_current_actor(request), customer_id))

    @extend_schema(
        tags=TAG,
        summary="Update contact data (type and NIT/document are immutable)",
        request=CustomerUpdateSerializer,
        responses=CustomerSerializer,
    )
    def patch(self, request: Request, customer_id: UUID) -> Response:
        payload = CustomerUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        view = customer_use_cases().update_customer(
            get_current_actor(request), customer_id, UpdateCustomerCommand(**payload.validated_data)
        )
        return _customer(view)


class CustomerByTaxIdView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="customers_by_tax_id",
        summary="Find a customer by NIT or document number (unified profile)",
        responses=CustomerSerializer,
    )
    def get(self, request: Request, tax_id: str) -> Response:
        view = customer_use_cases().get_customer_by_tax_id(get_current_actor(request), tax_id)
        return _customer(view)


class CustomerActivateView(APIView):
    @extend_schema(
        tags=TAG, summary="Reactivate a customer", request=None, responses=CustomerSerializer
    )
    def post(self, request: Request, customer_id: UUID) -> Response:
        return _customer(
            customer_use_cases().activate_customer(get_current_actor(request), customer_id)
        )


class CustomerDeactivateView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Deactivate a customer (its profile becomes read-only)",
        request=None,
        responses=CustomerSerializer,
    )
    def post(self, request: Request, customer_id: UUID) -> Response:
        return _customer(
            customer_use_cases().deactivate_customer(get_current_actor(request), customer_id)
        )


class CustomerHistoryView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Quotations and work orders of the customer, newest first",
        parameters=[PageQuerySerializer],
        responses=HistoryPageSerializer,
    )
    def get(self, request: Request, customer_id: UUID) -> Response:
        page = customer_use_cases().customer_history(
            get_current_actor(request), customer_id, _page_request(request)
        )
        return Response(page_payload(page, HistoryEntrySerializer))


class NoteListCreateView(APIView):
    @extend_schema(
        tags=TAG,
        operation_id="customer_notes_list",
        summary="Internal commercial notes, newest first",
        parameters=[PageQuerySerializer],
        responses=NotePageSerializer,
    )
    def get(self, request: Request, customer_id: UUID) -> Response:
        page = customer_use_cases().list_notes(
            get_current_actor(request), customer_id, _page_request(request)
        )
        return Response(page_payload(page, NoteSerializer))

    @extend_schema(
        tags=TAG,
        summary="Add an internal note",
        request=NoteInputSerializer,
        responses={201: NoteSerializer},
    )
    def post(self, request: Request, customer_id: UUID) -> Response:
        payload = NoteInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        note = customer_use_cases().add_note(
            get_current_actor(request), customer_id, payload.validated_data["content"]
        )
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)


class NoteDetailView(APIView):
    @extend_schema(
        tags=TAG,
        summary="Edit a note (only its author)",
        request=NoteInputSerializer,
        responses=NoteSerializer,
    )
    def patch(self, request: Request, customer_id: UUID, note_id: UUID) -> Response:
        payload = NoteInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        note = customer_use_cases().edit_note(
            get_current_actor(request), customer_id, note_id, payload.validated_data["content"]
        )
        return Response(NoteSerializer(note).data)

    @extend_schema(
        tags=TAG, summary="Delete a note (its text is kept in the audit log)", responses={204: None}
    )
    def delete(self, request: Request, customer_id: UUID, note_id: UUID) -> Response:
        customer_use_cases().delete_note(get_current_actor(request), customer_id, note_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
