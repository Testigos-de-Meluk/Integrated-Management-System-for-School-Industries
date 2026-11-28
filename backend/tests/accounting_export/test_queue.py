"""Siigo export queue (step 5c): fed by work order events, shows the current O.T. data."""

from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command

from modules.accounting_export.application.export_queue_service import ExportQueueService
from modules.accounting_export.domain.queue_entry import QueueEntry, QueueStatus
from modules.accounting_export.infrastructure.models import QueueEntryModel
from modules.accounting_export.ports.inbound.export_queue import QueueFilters
from modules.accounting_export.ports.outbound.ports import QueuedWorkOrders, QueueRepository
from modules.shared_kernel.domain.exceptions import PermissionDeniedError, ValidationError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, RoleType
from modules.work_orders.infrastructure.models import WorkOrderModel

from ..work_orders.test_api import approved_quotation

NOW = datetime(2026, 11, 27, 15, tzinfo=UTC)
OPERATOR = Actor.for_role(RoleType.OPERATOR, user_id=uuid4())
QUEUE = "/api/accounting-export/queue/"


# --- Domain and service with fakes ---------------------------------------------------------------


def test_withdraw_only_affects_pending_entries():
    entry = QueueEntry.enqueue(uuid4(), NOW)
    assert entry.withdraw(NOW) and entry.status is QueueStatus.WITHDRAWN
    assert not entry.withdraw(NOW)  # already withdrawn
    exported = QueueEntry(uuid4(), NOW, status=QueueStatus.EXPORTED)
    assert not exported.withdraw(NOW)  # annulled after export: Siigo is fixed by hand


class MemoryQueue(QueueRepository):
    def __init__(self):
        self.entries = {}

    def add(self, entry):
        if entry.work_order_id in self.entries:
            return False
        self.entries[entry.work_order_id] = entry
        return True

    def update(self, entry):
        self.entries[entry.work_order_id] = entry

    def for_work_order(self, work_order_id):
        return self.entries.get(work_order_id)

    def pending(self):
        return {k: e for k, e in self.entries.items() if e.is_pending}


class NoWorkOrders(QueuedWorkOrders):
    def __init__(self, pending=frozenset()):
        self.pending = pending

    def search_among(self, work_order_ids, search, page_request):
        return Page([], 0, page_request)

    def pending_ids(self):
        return self.pending


def test_enqueue_is_idempotent_and_sync_repairs_the_queue():
    kept, missing, gone = uuid4(), uuid4(), uuid4()
    queue = MemoryQueue()
    service = ExportQueueService(queue, NoWorkOrders(frozenset({kept, missing})), lambda: NOW)
    service.enqueue(kept)
    service.enqueue(kept)  # a repeated event never duplicates (US 2.30.4)
    service.enqueue(gone)

    result = service.sync()

    assert (result.enqueued, result.withdrawn) == (1, 1)
    assert set(queue.pending()) == {kept, missing}
    assert queue.entries[gone].status is QueueStatus.WITHDRAWN
    assert service.sync().enqueued == 0  # safe to repeat


def test_permission_and_date_range():
    service = ExportQueueService(MemoryQueue(), NoWorkOrders(), lambda: NOW)
    no_access = Actor.for_role(RoleType.OPERATOR, user_id=uuid4())
    object.__setattr__(no_access, "permissions", frozenset())
    with pytest.raises(PermissionDeniedError):
        service.list_pending(no_access, QueueFilters(), PageRequest())
    with pytest.raises(ValidationError):
        service.list_pending(
            OPERATOR,
            QueueFilters(created_from=NOW.date(), created_to=NOW.date() - timedelta(days=1)),
            PageRequest(),
        )


# --- Through the API, with the real event bus ---------------------------------------------------


@pytest.fixture
def admin(logged_in_client):
    return logged_in_client(RoleType.ADMIN)


@pytest.fixture
def operator(logged_in_client):
    return logged_in_client(RoleType.OPERATOR)


@pytest.fixture
def catalog(admin):
    def create(code, name):
        return admin.post(
            "/api/products/", {"code": code, "name": name, "unit_of_measure": "Unidad"}, "json"
        ).json()["id"]

    return {"chair": create("SIL-001", "Silla escolar"), "desk": create("MES-002", "Mesa")}


@pytest.fixture
def customer(admin):
    return admin.post(
        "/api/customers/",
        {
            "customer_type": "LEGAL_ENTITY",
            "tax_id": "800197268-4",
            "name": "Colegio Los Robles SAS",
            "address": "Calle 1 # 2-3",
            "primary_phone": "6011234567",
            "email": "compras@robles.edu.co",
        },
        "json",
    ).json()


def generate(admin, operator, catalog, customer):
    quotation_id = approved_quotation(admin, catalog)
    return operator.post(
        "/api/work-orders/", {"quotation_id": quotation_id, "customer_id": customer["id"]}, "json"
    ).json()


@pytest.mark.django_db
def test_generated_orders_enter_and_annulled_ones_leave(admin, operator, catalog, customer):
    first = generate(admin, operator, catalog, customer)
    second = generate(admin, operator, catalog, customer)

    queue = operator.get(QUEUE).json()
    assert [e["number"] for e in queue["results"]] == [first["number"], second["number"]]
    entry = queue["results"][0]
    assert entry["customer_name"] == "Colegio Los Robles SAS" and entry["enqueued_at"]
    assert [i["quantity"] for i in entry["items"]] == [40, 10]

    # Edited while Pendiente: the queue shows the current data of the O.T.
    operator.patch(
        f"/api/work-orders/{first['id']}/",
        {
            "customer_id": customer["id"],
            "items": [{"product_id": catalog["chair"], "quantity": 7}],
            "agreed_delivery_date": first["agreed_delivery_date"],
        },
        "json",
    )
    edited = operator.get(QUEUE, {"number": first["number"]}).json()["results"][0]
    assert [i["quantity"] for i in edited["items"]] == [7]

    operator.post(f"/api/work-orders/{first['id']}/cancel/", {"reason": "Duplicada"}, "json")

    assert [e["number"] for e in operator.get(QUEUE).json()["results"]] == [second["number"]]
    stored = QueueEntryModel.objects.get(work_order_id=first["id"])
    assert stored.status == "WITHDRAWN" and stored.withdrawn_at  # kept, never deleted


@pytest.mark.django_db
def test_filters(admin, operator, catalog, customer):
    order = generate(admin, operator, catalog, customer)
    today = order["created_at"][:10]

    assert operator.get(QUEUE, {"customer": "robles"}).json()["count"] == 1
    assert operator.get(QUEUE, {"customer": "otro"}).json()["count"] == 0
    assert operator.get(QUEUE, {"created_from": today, "created_to": today}).json()["count"] == 1
    assert operator.get(QUEUE, {"number": "OT-1999"}).json()["count"] == 0


@pytest.mark.django_db
def test_sync_command_adds_missing_pending_orders(admin, operator, catalog, customer):
    order = generate(admin, operator, catalog, customer)
    QueueEntryModel.objects.all().delete()  # as if the O.T. existed before the queue

    out = StringIO()
    call_command("sync_export_queue", stdout=out)
    call_command("sync_export_queue", stdout=out)

    assert "1 enqueued" in out.getvalue() and "0 enqueued" in out.getvalue()
    assert QueueEntryModel.objects.filter(work_order_id=order["id"]).count() == 1


@pytest.mark.django_db
def test_exported_orders_are_not_in_the_queue(admin, operator, catalog, customer):
    order = generate(admin, operator, catalog, customer)
    WorkOrderModel.objects.filter(pk=order["id"]).update(status="REGISTERED_IN_SIIGO")
    QueueEntryModel.objects.filter(work_order_id=order["id"]).update(status="EXPORTED")  # 5d

    assert operator.get(QUEUE).json()["count"] == 0
    operator.post(f"/api/work-orders/{order['id']}/cancel/", {"reason": "Error"}, "json")
    assert QueueEntryModel.objects.get(work_order_id=order["id"]).status == "EXPORTED"
