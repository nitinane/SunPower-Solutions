"""Calendar arithmetic and business-day (Asia/Kolkata) helpers."""

from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("Asia/Kolkata")


def add_months(value: date, months: int) -> date:
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    return date(year, month, min(value.day, monthrange(year, month)[1]))


def today_ist(now: datetime | None = None) -> date:
    """Business 'today' in India."""
    return (now or datetime.now(UTC)).astimezone(BUSINESS_TZ).date()


def ist_day_start(day: date) -> datetime:
    """00:00 Asia/Kolkata on `day`, as a UTC timestamp."""
    return datetime.combine(day, time.min, tzinfo=BUSINESS_TZ).astimezone(UTC)


def ist_day_bounds(first: date, last: date | None = None) -> tuple[datetime, datetime]:
    """[start of `first`, start of the day after `last`) in UTC."""
    return ist_day_start(first), ist_day_start((last or first) + timedelta(days=1))


def ist_date(value: datetime | None) -> date | None:
    return value.astimezone(BUSINESS_TZ).date() if value else None
