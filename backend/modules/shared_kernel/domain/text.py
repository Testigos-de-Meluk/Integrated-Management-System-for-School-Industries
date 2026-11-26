"""Text rules shared by the domain layer of every module.

Names (of users, products and customers) follow the same rule everywhere: inner whitespace is
collapsed and the field cannot be blank or longer than its maximum. Keeping one copy avoids the
three slightly diverging versions this module replaces.
"""

REQUIRED = "Este campo es obligatorio."


def clean_text(
    value: str | None,
    field_name: str,
    max_length: int,
    errors: dict[str, list[str]],
    *,
    required: bool = True,
) -> str:
    """Normalizes ``value`` and records a message in ``errors`` if it is blank or too long."""
    cleaned = " ".join((value or "").split())
    if required and not cleaned:
        errors[field_name] = [REQUIRED]
    elif len(cleaned) > max_length:
        errors[field_name] = [f"Máximo {max_length} caracteres."]
    return cleaned
