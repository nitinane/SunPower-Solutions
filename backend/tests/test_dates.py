from datetime import date

import pytest

from app.core.dates import add_months


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2027, 1, 31), 1, date(2027, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2027, 1, 31), 240, date(2047, 1, 31)),
        (date(2028, 2, 29), 12, date(2029, 2, 28)),
        (date(2026, 12, 15), 2, date(2027, 2, 15)),
    ],
)
def test_add_months(start, months, expected):
    assert add_months(start, months) == expected
