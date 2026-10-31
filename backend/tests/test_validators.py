"""Unit tests for app/core/validators.py — pure functions, no database needed."""

from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.core.validators import (
    IndianPhone,
    Money,
    OptionalEmail,
    Pincode,
    clean_name,
    clean_optional_text,
    normalize_email,
    normalize_indian_phone,
    normalize_pincode,
    normalize_serial,
    to_money,
)


# ------------------------------------------------------------------ phone

@pytest.mark.parametrize(
    "raw",
    ["9876543210", "+91 98765 43210", "+91-98765-43210", "09876543210",
     "919876543210", "(+91) 98765 43210", 9876543210],
)
def test_phone_all_formats_become_one(raw):
    assert normalize_indian_phone(raw) == "+919876543210"


@pytest.mark.parametrize("raw", ["", "12345", "5876543210", "98765432101", "abcdefghij", None])
def test_phone_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_indian_phone(raw)


# ------------------------------------------------------------------ pincode

@pytest.mark.parametrize("raw", ["110001", " 110 001 ", 110001])
def test_pincode_valid(raw):
    assert normalize_pincode(raw) == "110001"


@pytest.mark.parametrize("raw", ["011001", "11001", "1100011", "abcdef", "", None])
def test_pincode_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_pincode(raw)


# ------------------------------------------------------------------ serial

@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" inv-2304 0001\n", "INV-23040001"), ("abc/12", "ABC/12"), ("A" * 64, "A" * 64)],
)
def test_serial_cleaned(raw, expected):
    assert normalize_serial(raw) == expected


@pytest.mark.parametrize("raw", ["", "ab", "INV#001", "-ABC", "A" * 65, None])
def test_serial_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_serial(raw)


# ------------------------------------------------------------------ email

def test_email_lowercased_and_trimmed():
    assert normalize_email("  Ravi@Mail.COM ") == "ravi@mail.com"


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_email_empty_becomes_none(raw):
    assert normalize_email(raw) is None


@pytest.mark.parametrize("raw", ["ravi@", "ravi.mail.com", "ravi@mail"])
def test_email_rejects_invalid(raw):
    with pytest.raises(ValueError):
        normalize_email(raw)


# ------------------------------------------------------------------ text

def test_name_squashes_spaces():
    assert clean_name("  ravi   kumar ") == "ravi kumar"


@pytest.mark.parametrize("raw", ["a", "   ", "x" * 101, None])
def test_name_rejects_invalid(raw):
    with pytest.raises(ValueError):
        clean_name(raw)


def test_optional_text_keeps_inner_newlines():
    assert clean_optional_text("  line one\nline two  ") == "line one\nline two"


@pytest.mark.parametrize("raw", [None, "", "    "])
def test_optional_text_empty_becomes_none(raw):
    assert clean_optional_text(raw) is None


# ------------------------------------------------------------------ money

@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1500", "1500.00"), (0.1 + 0.2, "0.30"), ("2.345", "2.35"), ("2.344", "2.34"), (Decimal("7"), "7.00")],
)
def test_money_always_two_decimals(raw, expected):
    assert str(to_money(raw)) == expected


@pytest.mark.parametrize("raw", ["abc", None, "NaN", "Infinity"])
def test_money_rejects_invalid(raw):
    with pytest.raises(ValueError):
        to_money(raw)


# ------------------------------------------------------------------ inside a Pydantic schema

class _Form(BaseModel):
    phone: IndianPhone
    pincode: Pincode
    email: OptionalEmail = None
    amount: Money


def test_annotated_types_clean_inside_schema():
    form = _Form(phone="098765 43210", pincode=" 110001", email=" A@B.COM ", amount="10")
    assert form.phone == "+919876543210"
    assert form.pincode == "110001"
    assert form.email == "a@b.com"
    assert form.model_dump(mode="json")["amount"] == "10.00"


def test_schema_turns_value_error_into_validation_error():
    with pytest.raises(ValidationError) as exc:
        _Form(phone="123", pincode="110001", amount="1")
    assert "valid 10-digit Indian mobile" in str(exc.value)
    