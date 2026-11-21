"""Maps the ``Product`` domain entity to and from its Django model."""

from modules.products.domain.product import Product, ProductStatus
from modules.products.infrastructure.models import ProductModel


def to_domain(model: ProductModel) -> Product:
    return Product(
        id=model.id,
        code=model.code,
        name=model.name,
        unit_of_measure=model.unit_of_measure,
        status=ProductStatus(model.status),
    )


def apply_to_model(product: Product, model: ProductModel) -> ProductModel:
    model.id = product.id
    model.code = product.code
    model.name = product.name
    model.unit_of_measure = product.unit_of_measure
    model.status = product.status.value
    return model
