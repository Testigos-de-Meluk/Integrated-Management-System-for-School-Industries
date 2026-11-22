"""Identification numbers of customers (FR-02-09).

- Natural person: ID document number, 5 to 15 digits (dots and spaces are ignored).
- Legal entity: NIT of 9 digits plus its check digit (DV), validated with the DIAN algorithm and
  stored as ``900456789-1``.
"""

import re

NATURAL_MIN_DIGITS = 5
NATURAL_MAX_DIGITS = 15
NIT_DIGITS = 9

# DIAN weights, applied from the rightmost digit of the NIT to the left.
_DIAN_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)
_SEPARATORS = re.compile(r"[.\s]")


def nit_check_digit(nit: str) -> int:
    """Check digit (DV) of a NIT according to the DIAN modulo-11 algorithm."""
    # strict=False on purpose: a NIT has fewer digits than there are DIAN weights.
    pairs = zip(reversed(nit), _DIAN_WEIGHTS, strict=False)
    total = sum(int(digit) * weight for digit, weight in pairs)
    remainder = total % 11
    return remainder if remainder in (0, 1) else 11 - remainder


def normalize_natural_id(raw: str) -> str | None:
    """Returns the digits of an ID document, or ``None`` if it is not valid."""
    digits = _SEPARATORS.sub("", raw or "")
    if digits.isdigit() and NATURAL_MIN_DIGITS <= len(digits) <= NATURAL_MAX_DIGITS:
        return digits
    return None


def normalize_nit(raw: str) -> tuple[str | None, str | None]:
    """Returns ``(normalized NIT, error message)``.

    Accepts ``900.456.789-1``, ``900456789-1`` or ``9004567891`` (the last digit is the DV).
    """
    value = _SEPARATORS.sub("", raw or "")
    if "-" in value:
        base, _, check = value.partition("-")
    elif len(value) == NIT_DIGITS + 1:
        base, check = value[:-1], value[-1]
    else:
        base, check = value, ""

    if not (base.isdigit() and len(base) == NIT_DIGITS and check.isdigit() and len(check) == 1):
        return None, "Ingrese el NIT con su dígito de verificación (por ejemplo, 900456789-1)."
    if nit_check_digit(base) != int(check):
        return None, "El dígito de verificación del NIT no es válido."
    return f"{base}-{check}", None


def search_key(raw: str) -> str:
    """What to look for when a user types part of a NIT or document number."""
    return _SEPARATORS.sub("", raw or "")
