"""Pagination value objects (NFR-02-01, NFR-07-02: never more than 50 records per page)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .exceptions import ValidationError

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class PageRequest:
    page: int = 1
    size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        errors: dict[str, list[str]] = {}
        if self.page < 1:
            errors["page"] = ["La página debe ser mayor o igual a 1."]
        if not 1 <= self.size <= MAX_PAGE_SIZE:
            errors["page_size"] = [f"El tamaño de página debe estar entre 1 y {MAX_PAGE_SIZE}."]
        if errors:
            raise ValidationError(errors)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: Sequence[T]
    total: int
    request: PageRequest

    @property
    def total_pages(self) -> int:
        return math.ceil(self.total / self.request.size) if self.total else 0
