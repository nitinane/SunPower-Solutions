"""Calendar arithmetic for warranty dates."""

from calendar import monthrange
from datetime import date


def add_months(value: date, months: int) -> date:
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))
