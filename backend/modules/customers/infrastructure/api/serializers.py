"""DTOs of the Customers REST API."""

from rest_framework import serializers

from modules.customers.ports.inbound.customer_use_cases import (
    ADDRESS_MAX_LENGTH,
    CONTACT_MAX_LENGTH,
    CUSTOMER_STATUSES,
    CUSTOMER_TYPES,
    EMAIL_MAX_LENGTH,
    NAME_MAX_LENGTH,
    NOTE_MAX_LENGTH,
    PHONE_MAX_LENGTH,
)
from modules.shared_kernel.infrastructure.api.pagination import PageQuerySerializer, page_serializer

TYPE_CHOICES = [(t, t) for t in CUSTOMER_TYPES]
STATUS_CHOICES = [(s, s) for s in CUSTOMER_STATUSES]


class CustomerSerializer(serializers.Serializer):
    """Serializes a ``CustomerView`` DTO."""

    id = serializers.UUIDField(read_only=True)
    customer_type = serializers.ChoiceField(choices=TYPE_CHOICES, read_only=True)
    tax_id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    address = serializers.CharField(read_only=True)
    primary_phone = serializers.CharField(read_only=True)
    email = serializers.CharField(read_only=True)
    commercial_contact = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, read_only=True)
    is_active = serializers.BooleanField(read_only=True)


CustomerPageSerializer = page_serializer("CustomerPage", CustomerSerializer)


class CustomerQuerySerializer(PageQuerySerializer):
    tax_id = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    commercial_contact = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)


class _EditableFields(serializers.Serializer):
    name = serializers.CharField(max_length=NAME_MAX_LENGTH)
    address = serializers.CharField(max_length=ADDRESS_MAX_LENGTH)
    primary_phone = serializers.CharField(max_length=PHONE_MAX_LENGTH)
    email = serializers.CharField(max_length=EMAIL_MAX_LENGTH)  # format checked by the domain
    commercial_contact = serializers.CharField(
        max_length=CONTACT_MAX_LENGTH, required=False, allow_blank=True, default=""
    )


class CustomerCreateSerializer(_EditableFields):
    customer_type = serializers.ChoiceField(choices=TYPE_CHOICES)
    tax_id = serializers.CharField(max_length=30)


class CustomerUpdateSerializer(_EditableFields):
    """``customer_type`` and ``tax_id`` are not accepted: they can never change (FR-02-10)."""


class HistoryEntrySerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=["QUOTATION", "WORK_ORDER"])
    reference = serializers.CharField()
    date = serializers.DateTimeField()
    status = serializers.CharField()


HistoryPageSerializer = page_serializer("CustomerHistoryPage", HistoryEntrySerializer)


class NoteSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    content = serializers.CharField()
    author_name = serializers.CharField()
    created_at = serializers.DateTimeField()
    is_edited = serializers.BooleanField()
    updated_at = serializers.DateTimeField(allow_null=True)
    updated_by_name = serializers.CharField()
    can_edit = serializers.BooleanField(help_text="The current user wrote this note")


NotePageSerializer = page_serializer("CommercialNotePage", NoteSerializer)


class NoteInputSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=NOTE_MAX_LENGTH, allow_blank=True)
