from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.common import ErrorResponse, Page
from app.schemas.enquiries import (
    EnquiryClose,
    EnquiryPublicCreate,
    EnquiryPublicReceipt,
    EnquiryQualify,
    EnquiryRead,
    EnquiryStaffCreate,
)


def public_payload() -> dict[str, object]:
    return {
        "contact_name": " Nitin Madanala ",
        "phone": " 98765-43210 ",
        "email": " NITIN@example.com ",
        "address_line": " 12 Solar Street ",
        "city": " Hyderabad ",
        "state": " Telangana ",
        "pincode": "500032",
        "customer_type": "residential",
        "system_type": "on_grid",
        "requested_capacity_kw": "3.0",
        "subsidy_requested": True,
        "notes": "Call after 5 PM",
        "website_url": "",
    }


def test_public_create_preserves_typed_phone_and_normalizes_email() -> None:
    schema = EnquiryPublicCreate.model_validate(public_payload())
    assert schema.phone == " 98765-43210 "
    assert schema.email == "nitin@example.com"
    assert schema.contact_name == "Nitin Madanala"
    assert schema.requested_capacity_kw == Decimal("3.0")


def test_public_create_rejects_filled_honeypot() -> None:
    payload = public_payload()
    payload["website_url"] = "https://bot.example"
    with pytest.raises(ValidationError):
        EnquiryPublicCreate.model_validate(payload)


def test_public_create_rejects_invalid_phone_and_pincode() -> None:
    payload = public_payload()
    payload["phone"] = "123"
    with pytest.raises(ValidationError):
        EnquiryPublicCreate.model_validate(payload)

    payload = public_payload()
    payload["pincode"] = "12345"
    with pytest.raises(ValidationError):
        EnquiryPublicCreate.model_validate(payload)


def test_staff_create_rejects_website_source() -> None:
    payload = public_payload()
    payload.pop("website_url")
    payload["source"] = "website"
    with pytest.raises(ValidationError):
        EnquiryStaffCreate.model_validate(payload)


def test_qualification_and_close_action_constraints() -> None:
    EnquiryQualify.model_validate(
        {
            "shadow_free_roof_area_sqft": "500.00",
            "monthly_bill_amount": "2400.00",
            "grid_connection_suitable": True,
            "outcome": "qualified",
        }
    )
    with pytest.raises(ValidationError):
        EnquiryClose(reason="  ")


def test_enquiry_read_uses_service_overdue_value_and_excludes_private_key() -> None:
    now = datetime.now(UTC)
    payload = {
        "id": 12,
        "customer_id": None,
        "site_id": None,
        "contact_name": "Test Customer",
        "phone_raw": "9876543210",
        "phone_e164": "+919876543210",
        "email": None,
        "source": "website",
        "status": "new",
        "notes": None,
        "address_line": "12 Solar Street",
        "city": "Hyderabad",
        "state": "Telangana",
        "pincode": "500032",
        "requested_capacity_kw": Decimal("3.0"),
        "system_type": "on_grid",
        "customer_type": "residential",
        "subsidy_requested": False,
        "shadow_free_roof_area_sqft": None,
        "monthly_bill_amount": None,
        "grid_connection_suitable": None,
        "assigned_to": None,
        "qualified_by": None,
        "qualified_at": None,
        "close_reason": None,
        "created_at": now,
        "updated_at": now,
        "idempotency_key": "must-not-be-exposed",
    }
    schema = EnquiryRead.model_validate(payload)
    assert schema.is_overdue is False
    payload["is_overdue"] = True
    schema = EnquiryRead.model_validate(payload)
    assert schema.is_overdue is True
    assert "idempotency_key" not in schema.model_dump()


def test_common_schemas_match_api_shapes() -> None:
    page = Page[int](items=[1, 2], total=2, page=1, page_size=20)
    assert page.items == [1, 2]
    error = ErrorResponse.model_validate(
        {"error": {"code": "not_found", "message": "Enquiry not found"}}
    )
    assert error.error.code == "not_found"
    receipt = EnquiryPublicReceipt(reference="ENQ-000123", message="We received your enquiry")
    assert receipt.reference == "ENQ-000123"
