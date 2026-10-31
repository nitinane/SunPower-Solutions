"""
Shared input cleaning + validation, used by schemas (and services when needed).

Every rule mirrors a DB CHECK constraint, so bad input gets a friendly 422 message
from the API instead of a raw database error.

Usage in schemas:
    phone: PhoneInput              # validated, kept as typed (stored as phone_raw)
    phone: PhoneE164               # validated AND converted to +919876543210
    pincode: Pincode
    email: OptionalEmail = None
    email: RequiredEmail
    serial_number: SerialNumber
    contact_name: PersonName
    notes: OptionalText = None
"""

import re
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator

E164_PATTERN = re.compile(r"^\+[1-9][0-9]{7,14}$")        # same as DB CHECK phone_e164
PINCODE_PATTERN = re.compile(r"^[1-9][0-9]{5}$")          # Indian PIN: 6 digits, no leading 0
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SERIAL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\-_/.]{2,119}$")

DEFAULT_COUNTRY_CODE = "91"
PHONE_ERROR = "Enter a valid 10-digit phone number"


def normalize_phone(raw: str) -> str:
    """Convert an Indian or international phone number to E.164, e.g. +919876543210."""
    text = (raw or "").strip()
    has_plus = text.startswith("+")
    digits = re.sub(r"\D", "", text)

    if has_plus:                                                     # +91 98765 43210
        candidate = "+" + digits
    elif digits.startswith("00"):                                    # 0091 9876543210
        candidate = "+" + digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):               # 09876543210, 04023456789
        candidate = "+" + DEFAULT_COUNTRY_CODE + digits[1:]
    elif len(digits) == 12 and digits.startswith(DEFAULT_COUNTRY_CODE):  # 919876543210
        candidate = "+" + digits
    elif len(digits) == 10:                                          # 9876543210
        candidate = "+" + DEFAULT_COUNTRY_CODE + digits
    else:
        raise ValueError(PHONE_ERROR)

    if not E164_PATTERN.match(candidate):
        raise ValueError(PHONE_ERROR)
    if candidate.startswith("+91") and (len(candidate) != 13 or candidate[3] == "0"):
        raise ValueError(PHONE_ERROR)
    return candidate


def validate_phone_input(raw: str) -> str:
    """Check the phone can be normalized, but return it as typed (trimmed) for phone_raw."""
    cleaned = " ".join((raw or "").split())
    if len(cleaned) > 40:
        raise ValueError("Phone number is too long")
    normalize_phone(cleaned)
    return cleaned


def validate_pincode(raw: str) -> str:
    """Return a clean 6-digit Indian PIN code or raise."""
    cleaned = re.sub(r"\s", "", raw or "")
    if not PINCODE_PATTERN.match(cleaned):
        raise ValueError("Enter a valid 6-digit PIN code")
    return cleaned


def normalize_email(raw: object) -> str | None:
    """Trim + lowercase an email; empty becomes None; invalid raises."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("Email must be text")
    cleaned = raw.strip().lower()
    if not cleaned:
        return None
    if len(cleaned) > 255 or not EMAIL_PATTERN.match(cleaned):
        raise ValueError("Enter a valid email address")
    return cleaned


def require_email(raw: str) -> str:
    """Same as normalize_email, but empty is not allowed."""
    email = normalize_email(raw)
    if email is None:
        raise ValueError("Email is required")
    return email


def normalize_serial(raw: str) -> str:
    """Remove all spaces (scanners add them) and uppercase, e.g. ' inv-0091 ' -> 'INV-0091'."""
    cleaned = re.sub(r"\s", "", raw or "").upper()
    if not SERIAL_PATTERN.match(cleaned):
        raise ValueError("Serial number must be 3-120 letters or digits (- _ / . allowed)")
    return cleaned


def clean_name(raw: str) -> str:
    """Collapse extra spaces in a person's name and check its length."""
    cleaned = " ".join((raw or "").split())
    if len(cleaned) < 2:
        raise ValueError("Name must have at least 2 characters")
    if len(cleaned) > 150:
        raise ValueError("Name is too long")
    return cleaned


def clean_optional_text(raw: object) -> str | None:
    """Trim free text; empty becomes None (max length is set per field in the schema)."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("Must be text")
    cleaned = raw.strip()
    return cleaned or None


# ---------------------------------------------------------------- Ready-to-use schema types

PhoneInput = Annotated[str, AfterValidator(validate_phone_input)]
PhoneE164 = Annotated[str, AfterValidator(normalize_phone)]
Pincode = Annotated[str, AfterValidator(validate_pincode)]
OptionalEmail = Annotated[str | None, BeforeValidator(normalize_email)]
RequiredEmail = Annotated[str, AfterValidator(require_email)]
SerialNumber = Annotated[str, AfterValidator(normalize_serial)]
PersonName = Annotated[str, AfterValidator(clean_name)]
OptionalText = Annotated[str | None, BeforeValidator(clean_optional_text)]