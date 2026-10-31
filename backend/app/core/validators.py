"""
Input cleaners shared by schemas and services.

Each function takes messy human/scanner input and returns ONE clean format,
or raises ValueError. Pydantic turns that ValueError into a 422 response.

Why: "+91 98765 43210", "09876543210" and "9876543210" are the same customer.
If they are stored differently, UNIQUE(phone) cannot catch the duplicate.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated

from pydantic import BeforeValidator

_NON_DIGITS = re.compile(r"\D")
_WHITESPACE = re.compile(r"\s+")
_PINCODE = re.compile(r"^[1-9][0-9]{5}$")
_SERIAL = re.compile(r"^[A-Z0-9][A-Z0-9\-/]{2,63}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")
_MONEY_STEP = Decimal("0.01")


def normalize_indian_phone(raw: str | int | None) -> str:
    """'+91 98765-43210' / '09876543210' / '9876543210' -> '+919876543210'."""
    if raw is None:
        raise ValueError("Phone number is required")
    digits = _NON_DIGITS.sub("", str(raw))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "6789":
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return f"+91{digits}"


def normalize_pincode(raw: str | int | None) -> str:
    """' 110 001 ' -> '110001'. Indian PIN codes are 6 digits and never start with 0."""
    value = _WHITESPACE.sub("", str(raw if raw is not None else ""))
    if not _PINCODE.match(value):
        raise ValueError("Enter a valid 6-digit PIN code")
    return value


def normalize_serial(raw: str | None) -> str:
    """' inv-2304 0001\\n' -> 'INV-23040001'. Scanners add spaces/newlines; people type lowercase."""
    value = _WHITESPACE.sub("", str(raw if raw is not None else "")).upper()
    if not _SERIAL.match(value):
        raise ValueError("Serial number must be 3-64 characters: letters, digits, '-' or '/'")
    return value


def normalize_email(raw: str | None) -> str | None:
    """'  Ravi@Mail.COM ' -> 'ravi@mail.com'. Empty -> None (email is optional)."""
    if raw is None:
        return None
    value = str(raw).strip().lower()
    if not value:
        return None
    if len(value) > 254 or not _EMAIL.match(value):
        raise ValueError("Enter a valid email address")
    return value


def clean_name(raw: str | None) -> str:
    """'  ravi   kumar ' -> 'ravi kumar'. Required, 2-100 characters."""
    value = _WHITESPACE.sub(" ", str(raw if raw is not None else "")).strip()
    if not 2 <= len(value) <= 100:
        raise ValueError("Name must be 2-100 characters")
    return value


def clean_optional_text(raw: str | None) -> str | None:
    """Trim notes/addresses. Empty -> None, so the DB stores NULL instead of ''."""
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def to_money(value: object) -> Decimal:
    """Any number-like value -> Decimal with exactly 2 decimals (half-up). Never use float for money."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Enter a valid amount") from None
    if not amount.is_finite():
        raise ValueError("Enter a valid amount")
    return amount.quantize(_MONEY_STEP, rounding=ROUND_HALF_UP)


# Ready-made types for schemas: `phone: IndianPhone` cleans + validates automatically.
IndianPhone = Annotated[str, BeforeValidator(normalize_indian_phone)]
Pincode = Annotated[str, BeforeValidator(normalize_pincode)]
SerialNumber = Annotated[str, BeforeValidator(normalize_serial)]
PersonName = Annotated[str, BeforeValidator(clean_name)]
OptionalEmail = Annotated[str | None, BeforeValidator(normalize_email)]
OptionalText = Annotated[str | None, BeforeValidator(clean_optional_text)]
Money = Annotated[Decimal, BeforeValidator(to_money)]