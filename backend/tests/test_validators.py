"""Tests for app/core/validators.py: every rule that mirrors a DB CHECK constraint."""

import pytest
from pydantic import BaseModel, ValidationError

from app.core.validators import (
    OptionalEmail,
    OptionalText,
    PersonName,
    PhoneE164,
    PhoneInput,
    Pincode,
    RequiredEmail,
    SerialNumber,
    clean_name,
    clean_optional_text,
    normalize_email,
    normalize_phone,
    normalize_serial,
    require_email,
    validate_phone_input,
    validate_pincode,
)


# ---------------------------------------------------------------- Phone

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9876543210", "+919876543210"),
        ("98765 43210", "+919876543210"),
        ("09876543210", "+919876543210"),
        ("+91 98765-43210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("0091 9876543210", "+919876543210"),
        ("040-23456789", "+914023456789"),
        ("+14155552671", "+14155552671"),
    ],
)
def test_normalize_phone_valid(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "12345", "abcdefghij", "+91 0987654321", "98765432101234567", "+0123456789"],
)
def test_normalize_phone_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_validate_phone_input_keeps_raw_text() -> None:
    assert validate_phone_input("  98765   43210 ") == "98765 43210"


def test_validate_phone_input_rejects_bad_number() -> None:
    with pytest.raises(ValueError):
        validate_phone_input("123")


def test_validate_phone_input_rejects_too_long() -> None:
    with pytest.raises(ValueError):
        validate_phone_input("9" * 41)


# ---------------------------------------------------------------- Pincode

@pytest.mark.parametrize(("raw", "expected"), [("500081", "500081"), (" 500 081 ", "500081")])
def test_validate_pincode_valid(raw: str, expected: str) -> None:
    assert validate_pincode(raw) == expected


@pytest.mark.parametrize("raw", ["", "05008", "050081", "5000811", "50008a"])
def test_validate_pincode_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        validate_pincode(raw)


# ---------------------------------------------------------------- Email

def test_normalize_email_cleans_and_blanks_to_none() -> None:
    assert normalize_email("  Ravi@Example.COM ") == "ravi@example.com"
    assert normalize_email("") is None
    assert normalize_email("   ") is None
    assert normalize_email(None) is None


@pytest.mark.parametrize("raw", ["ravi", "ravi@", "ravi@example", "a b@example.com"])
def test_normalize_email_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_email(raw)


def test_require_email_rejects_blank() -> None:
    with pytest.raises(ValueError):
        require_email("   ")


# ---------------------------------------------------------------- Serial number

@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" inv-0091 ", "INV-0091"), ("ab 12 cd", "AB12CD"), ("sn/2304.01", "SN/2304.01")],
)
def test_normalize_serial_valid(raw: str, expected: str) -> None:
    assert normalize_serial(raw) == expected


@pytest.mark.parametrize("raw", ["", "ab", "-ABC123", "INV#001"])
def test_normalize_serial_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_serial(raw)


# ---------------------------------------------------------------- Names and free text

def test_clean_name_collapses_spaces() -> None:
    assert clean_name("  Ravi   Kumar ") == "Ravi Kumar"


@pytest.mark.parametrize("raw", ["", " ", "R", "x" * 151])
def test_clean_name_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        clean_name(raw)


def test_clean_optional_text() -> None:
    assert clean_optional_text("  hello ") == "hello"
    assert clean_optional_text("   ") is None
    assert clean_optional_text(None) is None


# ---------------------------------------------------------------- Types inside a real schema

class Sample(BaseModel):
    phone: PhoneInput
    phone_e164: PhoneE164
    pincode: Pincode
    email: OptionalEmail = None
    login_email: RequiredEmail
    serial: SerialNumber
    name: PersonName
    notes: OptionalText = None


def test_annotated_types_work_inside_a_schema() -> None:
    sample = Sample(
        phone=" 98765 43210 ",
        phone_e164="09876543210",
        pincode="500 081",
        email="",
        login_email="Ops@SunPower.in",
        serial=" inv-1 2 ",
        name=" Ravi  Kumar ",
        notes="  ",
    )
    assert sample.phone == "98765 43210"
    assert sample.phone_e164 == "+919876543210"
    assert sample.pincode == "500081"
    assert sample.email is None
    assert sample.login_email == "ops@sunpower.in"
    assert sample.serial == "INV-12"
    assert sample.name == "Ravi Kumar"
    assert sample.notes is None


def test_schema_error_contains_our_message() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Sample(
            phone="123",
            phone_e164="9876543210",
            pincode="500081",
            login_email="a@b.co",
            serial="ABC",
            name="Ravi",
        )
    messages = [error["msg"] for error in exc_info.value.errors()]
    assert any("Enter a valid 10-digit phone number" in message for message in messages)