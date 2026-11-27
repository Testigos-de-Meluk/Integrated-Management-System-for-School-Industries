"""Human references of business documents: ``COT-20261127-00042``, ``OT-20261127-00007``.

Format (step 5 decision, corrections README, summary item 16): prefix, the **local** creation date
(Colombia, so an order generated at 8 p.m. does not carry tomorrow's date) and a **global**
consecutive per document type that never restarts. Five digits are padded; past 99 999 the number
simply grows.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo("America/Bogota")
SEQUENCE_DIGITS = 5


def business_date(moment: datetime) -> date:
    """The calendar date in Colombia of an aware ``moment``."""
    return moment.astimezone(BUSINESS_TIMEZONE).date()


def document_number(prefix: str, created_at: datetime, sequence: int) -> str:
    if sequence < 1:
        raise ValueError("The sequence starts at 1.")
    return f"{prefix}-{business_date(created_at):%Y%m%d}-{sequence:0{SEQUENCE_DIGITS}d}"
