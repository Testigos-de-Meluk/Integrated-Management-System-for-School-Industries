"""Pure domain tests: no Django, no database."""

import pytest

from modules.products.domain.exceptions import InvalidProductStatusChange
from modules.products.domain.product import Product, ProductStatus
from modules.shared_kernel.domain.exceptions import ValidationError


def test_register_creates_an_active_product_with_normalized_values():
    product = Product.register("  sil-001 ", "  Silla   escolar ", "Unidad")

    assert product.code == "SIL-001"
    assert product.name == "Silla escolar"
    assert product.status is ProductStatus.ACTIVE
    assert product.is_selectable


def test_register_reports_every_missing_field():
    with pytest.raises(ValidationError) as error:
        Product.register("", " ", "")

    assert set(error.value.errors) == {"code", "name", "unit_of_measure"}


@pytest.mark.parametrize("code", ["SIL 001", "SIL_001", "-SIL", "Ñ-1", "X" * 31])
def test_register_rejects_invalid_codes(code):
    with pytest.raises(ValidationError) as error:
        Product.register(code, "Silla", "Unidad")

    assert "code" in error.value.errors


def test_update_details_changes_name_and_unit_but_never_the_code():
    product = Product.register("MES-002", "Mesa", "Unidad")

    product.update_details("Mesa bipersonal", "Juego")

    assert (product.code, product.name, product.unit_of_measure) == (
        "MES-002",
        "Mesa bipersonal",
        "Juego",
    )


def test_deactivate_and_activate_toggle_selectability():
    product = Product.register("PUP-003", "Pupitre", "Unidad")

    product.deactivate()
    assert product.status is ProductStatus.INACTIVE
    assert not product.is_selectable

    product.activate()
    assert product.is_selectable


def test_status_changes_to_the_same_status_are_rejected():
    product = Product.register("ESC-004", "Escritorio", "Unidad")

    with pytest.raises(InvalidProductStatusChange):
        product.activate()
    product.deactivate()
    with pytest.raises(InvalidProductStatusChange):
        product.deactivate()
