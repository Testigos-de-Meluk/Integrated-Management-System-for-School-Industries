"""Use-case tests with in-memory adapters: permissions, uniqueness and audit, without a database."""

from uuid import uuid4

import pytest

from modules.products.application.product_service import ProductService
from modules.products.domain.exceptions import (
    DUPLICATE_CODE_MESSAGE,
    DuplicateProductCode,
    ProductNotFound,
)
from modules.products.domain.product import ProductStatus
from modules.products.ports.inbound.product_use_cases import (
    ProductFilters,
    RegisterProductCommand,
    UpdateProductCommand,
)
from modules.shared_kernel.domain.audit import AuditAction
from modules.shared_kernel.domain.exceptions import PermissionDeniedError
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.domain.security import Actor, RoleType

from .fakes import InMemoryProductRepository, SpyAuditLogger

ADMIN = Actor.for_role(RoleType.ADMIN)
OPERATOR = Actor.for_role(RoleType.OPERATOR)


@pytest.fixture
def audit():
    return SpyAuditLogger()


@pytest.fixture
def service(audit):
    return ProductService(InMemoryProductRepository(), audit)


def register(service, code="SIL-001", name="Silla escolar", unit="Unidad", actor=ADMIN):
    return service.register_product(actor, RegisterProductCommand(code, name, unit))


def test_admin_registers_a_product_and_it_is_audited(service, audit):
    product = register(service)

    assert product.status is ProductStatus.ACTIVE
    assert [r.action for r in audit.records] == [AuditAction.CREATED]
    assert audit.records[0].new_values["code"] == "SIL-001"


def test_duplicate_code_is_rejected_even_with_different_case(service):
    register(service)

    with pytest.raises(DuplicateProductCode) as error:
        register(service, code="sil-001")

    assert error.value.errors == {"code": [DUPLICATE_CODE_MESSAGE]}


def test_operator_can_list_but_not_modify_the_catalog(service):
    product = register(service)

    page = service.list_products(OPERATOR, ProductFilters(), PageRequest())
    assert [p.code for p in page.items] == ["SIL-001"]

    with pytest.raises(PermissionDeniedError):
        register(service, code="MES-002", actor=OPERATOR)
    with pytest.raises(PermissionDeniedError):
        service.update_product(OPERATOR, product.id, UpdateProductCommand("X", "Unidad"))
    with pytest.raises(PermissionDeniedError):
        service.deactivate_product(OPERATOR, product.id)


def test_update_keeps_old_and_new_values_in_the_audit_log(service, audit):
    product = register(service)

    service.update_product(ADMIN, product.id, UpdateProductCommand("Silla infantil", "Unidad"))

    record = audit.records[-1]
    assert record.action is AuditAction.UPDATED
    assert record.old_values["name"] == "Silla escolar"
    assert record.new_values["name"] == "Silla infantil"


def test_deactivate_then_reactivate(service, audit):
    product = register(service)

    assert service.deactivate_product(ADMIN, product.id).status is ProductStatus.INACTIVE
    assert service.activate_product(ADMIN, product.id).status is ProductStatus.ACTIVE
    assert [r.action for r in audit.records][-2:] == [AuditAction.STATUS_CHANGED] * 2


def test_unknown_product_raises_not_found(service):
    with pytest.raises(ProductNotFound):
        service.get_product(ADMIN, uuid4())


def test_filters_are_combined(service):
    register(service, "SIL-001", "Silla escolar")
    register(service, "SIL-006", "Silla infantil")
    register(service, "MES-002", "Mesa bipersonal")
    service.deactivate_product(
        ADMIN,
        service.list_products(ADMIN, ProductFilters(code="SIL-006"), PageRequest()).items[0].id,
    )

    page = service.list_products(
        ADMIN, ProductFilters(name="silla", status=ProductStatus.ACTIVE), PageRequest()
    )

    assert [p.code for p in page.items] == ["SIL-001"]
