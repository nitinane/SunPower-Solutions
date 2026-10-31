"""Shared input normalizers and validators.

Keep these helpers independent of Pydantic, SQLAlchemy, and FastAPI so schemas,
services, and import jobs can reuse the same rules.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_E164_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")
_PINCODE_RE = re.compile(r"^[1-9][0-9]{5}$")


def normalize_phone(value: str) -> str:
    """Return a phone number in E.164 format.

    Ten-digit Indian mobile numbers are interpreted as +91. Explicitly
    international numbers must include a leading '+' (or '00' prefix).
    """
    if not isinstance(value, str):
        raise ValueError("Phone number must be text")

    raw = value.strip()
    if not raw:
        raise ValueError("Phone number is required")

    compact = re.sub(r"[\s().-]", "", raw)
    if compact.startswith("00"):
        compact = "+" + compact[2:]

    if compact.startswith("+"):
        digits = compact[1:]
        if not digits.isdigit():
            raise ValueError("Phone number contains invalid characters")
        normalized = "+" + digits
    else:
        digits = re.sub(r"\D", "", compact)
        if len(digits) == 10 and digits[0] in "6789":
            normalized = "+91" + digits
        elif len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
            normalized = "+91" + digits[1:]
        elif len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
            normalized = "+" + digits
        else:
            raise ValueError(
                "Use a valid Indian mobile number or include an international '+' prefix"
            )

    if not _E164_RE.fullmatch(normalized):
        raise ValueError("Phone number must be a valid E.164 number")
    return normalized


def validate_pincode(value: str) -> None:
    """Validate a six-digit Indian PIN code."""
    if not isinstance(value, str) or not _PINCODE_RE.fullmatch(value.strip()):
        raise ValueError("Pincode must be a valid six-digit Indian PIN code")


def normalize_serial(value: str) -> str:
    """Trim and uppercase a serialized-unit identifier."""
    if not isinstance(value, str):
        raise ValueError("Serial number must be text")
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("Serial number is required")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError("Serial number contains invalid characters")
    return normalized


def normalize_email(value: str) -> str:
    """Trim and lowercase an email address, rejecting malformed values."""
    if not isinstance(value, str):
        raise ValueError("Email address must be text")
    normalized = value.strip().lower()
    if len(normalized) > 255 or not _EMAIL_RE.fullmatch(normalized):
        raise ValueError("Enter a valid email address")
    return normalized
