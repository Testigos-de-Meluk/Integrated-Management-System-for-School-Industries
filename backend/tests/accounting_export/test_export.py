"""Export batches to Odoo (step 5d): the file, "Registrada en Odoo", batches and concurrency."""

import re
from datetime import UTC, date, datetime
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from modules.accounting_export.domain.export_batch import batch_file_name, validate_selection
from modules.accounting_export.infrastructure.files.odoo_sale_orders import (
    HEADERS,
    OdooSaleOrderXlsxFormatter,
)
from modules.accounting_export.infrastructure.models import ExportBatchModel, QueueEntryModel
from modules.accounting_export.ports.outbound.ports import QueuedLine, QueuedWorkOrder
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.infrastructure.models import AuditEntryModel
from modules.work_orders.infrastructure.models import WorkOrderModel

from .test_queue import generate

QUEUE = "/api/accounting-export/queue/"
BATCHES = "/api/accounting-export/batches/"


def rows_of(content: bytes) -> list[tuple]:
    sheet = load_workbook(BytesIO(content)).active
    return [tuple(row) for row in sheet.iter_rows(values_only=True)]


# --- Domain and formatter (no database) --------------------------------------------------------


def test_file_name_uses_colombian_time():
    moment = datetime(2026, 11, 28, 3, 4, 5, tzinfo=UTC)  # 22:04:05 of the 27th in Bogotá
    assert batch_file_name(moment, "xlsx") == "IMSI-Odoo-20261127-220405.xlsx"


def test_selection_must_not_be_empty_or_too_big():
    with pytest.raises(ValidationError):
        validate_selection(frozenset())
    with pytest.raises(ValidationError):
        validate_selection(frozenset(uuid4() for _ in range(201)))


def test_odoo_layout_one_row_per_item_order_fields_only_on_the_first():
    order = QueuedWorkOrder(
        id=uuid4(),
        number="OT-20261127-00042",
        quotation_number="COT-20261120-00007",
        created_at=datetime(2026, 11, 27, tzinfo=UTC),
        customer_tax_id="800197268-4",
        customer_name="Colegio Los Robles SAS",
        items=(
            QueuedLine("SIL-001", "Silla escolar", "Unidad", 40),
            QueuedLine("MES-002", "Mesa", "Unidad", 10),
        ),
        agreed_delivery_date=date(2026, 12, 15),
    )

    rows = rows_of(OdooSaleOrderXlsxFormatter().format([order]))

    assert rows[0] == HEADERS
    assert rows[1] == (
        "Colegio Los Robles SAS",
        "OT-20261127-00042",
        "COT-20261120-00007",
        datetime(2026, 12, 15, 12, 0),
        "SIL-001",
        "Silla escolar",
        40,
    )
    assert rows[2] == (None, None, None, None, "MES-002", "Mesa", 10)
    assert len(rows) == 3


# --- Through the API ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_export_registers_the_orders_and_keeps_the_file(admin, operator, catalog, customer):
    first = generate(admin, operator, catalog, customer)
    second = generate(admin, operator, catalog, customer)

    response = operator.post(BATCHES, {"work_order_ids": [second["id"], first["id"]]}, "json")

    assert response.status_code == 201
    batch = response.json()
    assert re.fullmatch(r"IMSI-Odoo-\d{8}-\d{6}\.xlsx", batch["file_name"])
    assert [o["number"] for o in batch["work_orders"]] == [first["number"], second["number"]]
    assert {o["status"] for o in batch["work_orders"]} == {"REGISTERED_IN_ACCOUNTING"}

    # The O.T.s left the queue, are read-only and can now be reconciled.
    assert operator.get(QUEUE).json()["count"] == 0
    detail = operator.get(f"/api/work-orders/{first['id']}/").json()
    assert detail["status"] == "REGISTERED_IN_ACCOUNTING"
    assert not detail["can_edit"] and detail["can_reconcile"] and detail["was_exported"]
    entries = QueueEntryModel.objects.filter(work_order_id__in=[first["id"], second["id"]])
    assert {(e.status, str(e.export_batch_id)) for e in entries} == {("EXPORTED", batch["id"])}

    # Audited: the batch and each status change.
    exported = AuditEntryModel.objects.get(action="EXPORTED", entity_type="ExportBatch")
    assert exported.new_values["work_orders"] == [first["number"], second["number"]]
    assert (
        AuditEntryModel.objects.filter(action="STATUS_CHANGED", entity_type="WorkOrder").count()
        == 2
    )

    # The stored file, downloaded again byte for byte.
    file = operator.get(f"{BATCHES}{batch['id']}/file/")
    assert file.status_code == 200
    assert file["Content-Disposition"] == f'attachment; filename="{batch["file_name"]}"'
    assert file.content == bytes(ExportBatchModel.objects.get(pk=batch["id"]).content)
    rows = rows_of(file.content)
    assert rows[0] == HEADERS
    assert [r[1] for r in rows[1:]] == [first["number"], None, second["number"], None]
    assert [(r[4], r[6]) for r in rows[1:3]] == [("SIL-001", 40), ("MES-002", 10)]


@pytest.mark.django_db
def test_an_order_already_exported_blocks_the_whole_batch(admin, operator, catalog, customer):
    first = generate(admin, operator, catalog, customer)
    second = generate(admin, operator, catalog, customer)
    assert operator.post(BATCHES, {"work_order_ids": [first["id"]]}, "json").status_code == 201

    # E.g. two people exporting at the same time: the second one gets a clear 409.
    response = operator.post(BATCHES, {"work_order_ids": [first["id"], second["id"]]}, "json")

    assert response.status_code == 409
    assert response.json()["code"] == "WORK_ORDERS_NOT_PENDING"
    assert first["number"] in response.json()["detail"]
    assert WorkOrderModel.objects.get(pk=second["id"]).status == "PENDING"  # all or nothing
    assert ExportBatchModel.objects.count() == 1
    assert [e["number"] for e in operator.get(QUEUE).json()["results"]] == [second["number"]]


@pytest.mark.django_db
def test_annulled_orders_cannot_be_exported(admin, operator, catalog, customer):
    order = generate(admin, operator, catalog, customer)
    operator.post(f"/api/work-orders/{order['id']}/cancel/", {"reason": "Duplicada"}, "json")

    response = operator.post(BATCHES, {"work_order_ids": [order["id"]]}, "json")

    assert response.status_code == 409 and order["number"] in response.json()["detail"]


@pytest.mark.django_db
def test_batches_list_flags_orders_annulled_after_export(admin, operator, catalog, customer):
    order = generate(admin, operator, catalog, customer)
    batch = operator.post(BATCHES, {"work_order_ids": [order["id"]]}, "json").json()
    operator.post(f"/api/work-orders/{order['id']}/cancel/", {"reason": "Cliente desistió"}, "json")

    listed = operator.get(BATCHES).json()

    assert listed["count"] == 1
    entry = listed["results"][0]
    assert entry["id"] == batch["id"] and entry["created_by_name"]
    assert entry["work_orders"][0]["status"] == "CANCELLED"
    assert entry["work_orders"][0]["cancelled_after_export"] is True
    assert QueueEntryModel.objects.get(work_order_id=order["id"]).status == "EXPORTED"


@pytest.mark.django_db
def test_validation_and_unknown_batch(operator):
    assert operator.post(BATCHES, {"work_order_ids": []}, "json").status_code == 400
    assert operator.post(BATCHES, {"work_order_ids": [str(uuid4())]}, "json").status_code == 409
    assert operator.get(f"{BATCHES}{uuid4()}/file/").status_code == 404
