"""Review use cases with in-memory adapters (no database, no PDF library)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from modules.customers.ports.inbound.customer_directory import CustomerSummary
from modules.quotations.application.estimators import StatisticalPriceEstimator
from modules.quotations.application.quotation_request_service import QuotationRequestService
from modules.quotations.application.quotation_review_service import (
    CustomerQuotationsService,
    QuotationReviewService,
)
from modules.quotations.domain.events import QuotationApproved
from modules.quotations.domain.exceptions import (
    ApprovalIncomplete,
    InvalidQuotationItems,
    QuotationLocked,
)
from modules.quotations.ports.inbound.quotation_requests import (
    RequestedItem,
    RequestQuotationCommand,
)
from modules.quotations.ports.inbound.quotation_review import (
    ApproveQuotationCommand,
    ItemPrice,
    ModifyQuotationCommand,
    QuotationFilters,
    ReviewedItem,
)
from modules.shared_kernel.domain.audit import AuditAction
from modules.shared_kernel.domain.exceptions import PermissionDeniedError, ValidationError
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.domain.security import Actor, RoleType

from ..shared_fakes import SpyAuditLogger, SpyEventPublisher, SpyNotifier
from .fakes import (
    BOARD,
    CHAIR,
    DESK,
    FakeCatalog,
    FakeCustomers,
    FakePdf,
    FixedHistory,
    MemoryRepository,
    NoDispatch,
    Numbers,
)

NOW = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)
LATER = NOW.date() + timedelta(days=20)
ADMIN = Actor.for_role(RoleType.ADMIN, user_id=uuid4(), display_name="Ana Admin")
OPERATOR = Actor.for_role(RoleType.OPERATOR, user_id=uuid4())
SCHOOL = CustomerSummary(uuid4(), "800197268-4", "Colegio Los Robles SAS", True)
CLOSED = CustomerSummary(uuid4(), "900456789-1", "Colegio Cerrado", False)


@pytest.fixture
def deps():
    return {
        "repository": MemoryRepository(),
        "notifier": SpyNotifier(),
        "events": SpyEventPublisher(),
        "audit": SpyAuditLogger(),
    }


@pytest.fixture
def review(deps):
    return QuotationReviewService(
        repository=deps["repository"],
        catalog=FakeCatalog(),
        customers=FakeCustomers(SCHOOL, CLOSED),
        price_estimator=StatisticalPriceEstimator(FixedHistory()),
        dispatch_estimator=NoDispatch(),
        documents=FakePdf(),
        notifier=deps["notifier"],
        events=deps["events"],
        audit_logger=deps["audit"],
        clock=lambda: NOW,
    )


@pytest.fixture
def pending(deps):
    """A preliminary quotation requested through the public assistant: chair priced, desk not."""
    requests = QuotationRequestService(
        repository=deps["repository"],
        numbers=Numbers(),
        catalog=FakeCatalog(),
        price_estimator=StatisticalPriceEstimator(FixedHistory()),
        dispatch_estimator=NoDispatch(),
        documents=FakePdf(),
        notifier=SpyNotifier(),
        audit_logger=SpyAuditLogger(),
        clock=lambda: NOW,
    )
    view = requests.request_quotation(
        RequestQuotationCommand(
            full_name="Laura Méndez",
            email="laura@colegio.edu.co",
            phone="310 456 7890",
            items=(RequestedItem(CHAIR.id, 40), RequestedItem(DESK.id, 10)),
            data_consent=True,
            tax_id="800.197.268",  # typed without the check digit
        ),
        None,
    )
    return view.id


def items_of(review, quotation_id):
    return {i.product_code: i for i in review.get_quotation(ADMIN, quotation_id).items}


def test_the_operator_cannot_review_quotations(review, pending):
    for call in (
        lambda: review.list_quotations(OPERATOR, QuotationFilters(), PageRequest()),
        lambda: review.get_quotation(OPERATOR, pending),
        lambda: review.reject_quotation(OPERATOR, pending, "No"),
    ):
        with pytest.raises(PermissionDeniedError):
            call()


def test_detail_suggests_the_customer_whose_nit_matches(review, pending):
    detail = review.get_quotation(ADMIN, pending)

    assert detail.customer is None
    assert detail.suggested_customer.id == SCHOOL.id
    assert detail.status == "PENDING_REVIEW" and detail.is_editable


def test_modify_keeps_estimates_adds_active_products_and_audits_the_reason(review, pending, deps):
    detail = review.modify_quotation(
        ADMIN,
        pending,
        ModifyQuotationCommand(
            items=(
                ReviewedItem(CHAIR.id, 30, Decimal(185000)),
                ReviewedItem(BOARD.id, 2),  # new product, DESK removed
            ),
            reason="El colegio pidió menos sillas",
            dispatch_date=LATER,
        ),
    )

    chair, board = detail.items
    assert detail.status == "MODIFIED"
    assert (chair.quantity, chair.unit_price_min, chair.final_unit_price) == (
        30,
        "170000",
        "185000",
    )
    assert board.product_code == "TAB-003" and board.unit_price_min is None
    assert detail.dispatch_date_source == "MANUAL"
    record = deps["audit"].records[-1]
    assert record.action is AuditAction.UPDATED and record.reason == "El colegio pidió menos sillas"
    assert record.old_values["items"][0]["quantity"] == 40


def test_modify_requires_a_reason_and_only_active_products(review, pending):
    with pytest.raises(ValidationError) as error:
        review.modify_quotation(
            ADMIN, pending, ModifyQuotationCommand((ReviewedItem(CHAIR.id, 1),), reason=" ")
        )
    assert "reason" in error.value.errors

    with pytest.raises(InvalidQuotationItems):
        review.modify_quotation(
            ADMIN, pending, ModifyQuotationCommand((ReviewedItem(uuid4(), 1),), reason="Cambio")
        )


def test_approve_needs_complete_prices(review, pending):
    chair = items_of(review, pending)["SIL-001"]
    with pytest.raises(ApprovalIncomplete):
        review.approve_quotation(
            ADMIN, pending, ApproveQuotationCommand((ItemPrice(chair.id, Decimal(180000)),), LATER)
        )


def test_approve_audits_publishes_the_event_and_emails_the_formal_pdf(review, pending, deps):
    items = items_of(review, pending)
    detail = review.approve_quotation(
        ADMIN,
        pending,
        ApproveQuotationCommand(
            prices=(
                ItemPrice(items["SIL-001"].id, Decimal(180000)),
                ItemPrice(items["MES-002"].id, Decimal(420000)),
            ),
            dispatch_date=LATER,
            commercial_terms="Pago contra entrega",
        ),
    )

    assert detail.status == "APPROVED" and not detail.is_editable
    assert detail.final_total == str(40 * 180000 + 10 * 420000)
    assert detail.approved_by_name == "Ana Admin"
    record = deps["audit"].records[-1]
    assert record.action is AuditAction.APPROVED and record.actor == ADMIN
    assert record.new_values["items"][0]["estimated_unit_min"] == "170000"
    (event,) = deps["events"].events
    assert isinstance(event, QuotationApproved) and event.quotation_id == pending
    (email,) = deps["notifier"].sent
    assert email.to == ("laura@colegio.edu.co",)
    assert email.attachments[0].content.startswith(b"%PDF-formal")
    assert review.document(ADMIN, pending).content.startswith(b"%PDF-formal")

    with pytest.raises(QuotationLocked):  # US 2.27.4
        review.reject_quotation(ADMIN, pending, "Tarde")


def test_reject_emails_the_reason(review, pending, deps):
    detail = review.reject_quotation(ADMIN, pending, "Fuera de la zona de despacho")

    assert detail.status == "REJECTED" and detail.rejection_reason == "Fuera de la zona de despacho"
    assert deps["audit"].records[-1].reason == "Fuera de la zona de despacho"
    assert "Fuera de la zona de despacho" in deps["notifier"].sent[0].body


def test_only_active_customers_can_be_linked_and_history_lists_them(review, pending, deps):
    with pytest.raises(ValidationError):
        review.link_customer(ADMIN, pending, CLOSED.id)

    detail = review.link_customer(ADMIN, pending, SCHOOL.id)
    assert detail.customer.name == SCHOOL.name and detail.suggested_customer is None

    history = CustomerQuotationsService(deps["repository"]).quotations_of(SCHOOL.id, PageRequest())
    assert [q.number for q in history.items] == [detail.number]


def test_list_validates_ranges(review):
    with pytest.raises(ValidationError):
        review.list_quotations(
            ADMIN,
            QuotationFilters(issued_from=LATER, issued_to=NOW.date()),
            PageRequest(),
        )
