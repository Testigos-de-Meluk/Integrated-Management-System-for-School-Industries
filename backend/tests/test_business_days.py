"""Colombian business days (step 5b): Monday to Friday minus public holidays."""

from datetime import date

import pytest

from modules.shared_kernel.domain.business_days import (
    add_business_days,
    business_days_between,
    colombian_holidays,
    easter_sunday,
    is_business_day,
)


def test_easter_dates():
    assert easter_sunday(2026) == date(2026, 4, 5)
    assert easter_sunday(2027) == date(2027, 3, 28)
    assert easter_sunday(2025) == date(2025, 4, 20)


def test_the_official_2026_holidays():
    expected = {
        (1, 1), (1, 12), (3, 23), (4, 2), (4, 3), (5, 1), (5, 18), (6, 8), (6, 15),
        (6, 29), (7, 20), (8, 7), (8, 17), (10, 12), (11, 2), (11, 16), (12, 8), (12, 25),
    }  # fmt: skip
    assert colombian_holidays(2026) == {date(2026, m, d) for m, d in expected}


def test_weekends_and_holidays_are_not_business_days():
    assert is_business_day(date(2026, 11, 27))  # Friday
    assert not is_business_day(date(2026, 11, 28))  # Saturday
    assert not is_business_day(date(2026, 11, 16))  # Monday, Independence of Cartagena
    assert not is_business_day(date(2026, 12, 25))


@pytest.mark.parametrize(
    ("start", "days", "expected"),
    [
        (date(2026, 11, 27), 0, date(2026, 11, 27)),
        (date(2026, 11, 27), 1, date(2026, 11, 30)),  # Friday + 1 → Monday
        (date(2026, 11, 13), 1, date(2026, 11, 17)),  # skips the Monday holiday
        (date(2026, 12, 24), 1, date(2026, 12, 28)),  # skips Christmas and the weekend
        (date(2026, 11, 28), 1, date(2026, 11, 30)),  # from a Saturday
    ],
)
def test_add_business_days(start, days, expected):
    assert add_business_days(start, days) == expected


def test_business_days_between_is_the_inverse_of_adding():
    start = date(2026, 11, 10)
    for days in range(30):
        assert business_days_between(start, add_business_days(start, days)) == days
    assert business_days_between(date(2026, 11, 27), date(2026, 11, 20)) == 0
