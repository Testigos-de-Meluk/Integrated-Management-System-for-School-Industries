"""Business days in Colombia: Monday to Friday, except public holidays (step 5b decision).

Holidays follow Law 51 of 1983 ("Ley Emiliani"):

* fixed dates that never move: 1 Jan, 1 May, 20 Jul, 7 Aug, 8 Dec, 25 Dec;
* dates moved to the following Monday when they fall on another day: 6 Jan, 19 Mar, 29 Jun,
  15 Aug, 12 Oct, 1 Nov, 11 Nov;
* dates tied to Easter: Holy Thursday and Good Friday (not moved), and Ascension, Corpus Christi
  and Sacred Heart (Easter + 39, + 60 and + 68 days, moved to the following Monday).

Pure Python, computed for any year (no external calendar to maintain).
"""

from datetime import date, timedelta
from functools import lru_cache

_FIXED = ((1, 1), (5, 1), (7, 20), (8, 7), (12, 8), (12, 25))
_MOVED_TO_MONDAY = ((1, 6), (3, 19), (6, 29), (8, 15), (10, 12), (11, 1), (11, 11))


def easter_sunday(year: int) -> date:
    """Gregorian Easter (anonymous algorithm, Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _next_monday(day: date) -> date:
    return day + timedelta(days=(7 - day.weekday()) % 7)


@lru_cache(maxsize=64)
def colombian_holidays(year: int) -> frozenset[date]:
    easter = easter_sunday(year)
    holidays = {date(year, month, day) for month, day in _FIXED}
    holidays |= {_next_monday(date(year, month, day)) for month, day in _MOVED_TO_MONDAY}
    holidays |= {easter - timedelta(days=3), easter - timedelta(days=2)}
    holidays |= {_next_monday(easter + timedelta(days=offset)) for offset in (39, 60, 68)}
    return frozenset(holidays)


def is_business_day(day: date) -> bool:
    return day.weekday() < 5 and day not in colombian_holidays(day.year)


def add_business_days(start: date, days: int) -> date:
    """The ``days``-th business day after ``start`` (``start`` itself does not count)."""
    if days < 0:
        raise ValueError("days must not be negative")
    current = start
    while days > 0:
        current += timedelta(days=1)
        if is_business_day(current):
            days -= 1
    return current


def business_days_between(start: date, end: date) -> int:
    """Business days after ``start`` up to ``end`` inclusive (0 when ``end`` <= ``start``)."""
    count, current = 0, start
    while current < end:
        current += timedelta(days=1)
        if is_business_day(current):
            count += 1
    return count
