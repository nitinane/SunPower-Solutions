"""Request and response schemas for customer enquiries."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import CustomerType, EnquirySource, EnquiryStatus, SystemType
from app.core.validators import normalize_email, normalize_phone, validate_pincode


class _EnquirySubmission(BaseModel):
    """Fields shared by public and staff-created enquiries."""

    model_config = ConfigDict(extra="forbid")

    contact_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=1, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    address_line: str = Field(min_length=1, max_length=240)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    pincode: str = Field(min_length=6, max_length=6)
    customer_type: CustomerType
    system_type: SystemType
    requested_capacity_kw: Decimal = Field(
        ge=Decimal("1"),
        le=Decimal("5"),
        max_digits=4,
        decimal_places=1,
    )
    subsidy_requested: bool
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator(
        "contact_name", "address_line", "city", "state"
    )
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field cannot be blank")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone_without_rewriting_input(cls, value: str) -> str:
        # The raw value is deliberately preserved. The service stores this as
        # phone_raw and separately stores normalize_phone(value) as phone_e164.
        normalize_phone(value)
        return value

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_email(value)

    @field_validator("pincode")
    @classmethod
    def validate_indian_pincode(cls, value: str) -> str:
        normalized = value.strip()
        validate_pincode(normalized)
        return normalized


class EnquiryPublicCreate(_EnquirySubmission):
    """Website enquiry input; ``website_url`` is a honeypot and must stay empty."""

    website_url: str = Field(default="", max_length=0)


class EnquiryStaffCreate(_EnquirySubmission):
    """Staff-entered enquiry with an explicit non-website source."""

    source: EnquirySource

    @field_validator("source")
    @classmethod
    def reject_website_source(cls, value: EnquirySource) -> EnquirySource:
        if value in {EnquirySource.WEB_FORM, EnquirySource.WEBSITE}:
            raise ValueError("Staff-created enquiries cannot use the website source")
        return value


class EnquiryAssign(BaseModel):
    """Assign an enquiry to an active staff user; activity/role checks belong in the service."""

    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)


class EnquiryQualify(BaseModel):
    """Submit survey/qualification facts and the desired workflow outcome."""

    model_config = ConfigDict(extra="forbid")

    shadow_free_roof_area_sqft: Decimal = Field(
        gt=Decimal("0"),
        max_digits=8,
        decimal_places=2,
    )
    monthly_bill_amount: Decimal = Field(
        ge=Decimal("0"),
        max_digits=12,
        decimal_places=2,
    )
    grid_connection_suitable: bool
    outcome: Literal["qualified", "unqualified", "contacted"]
    notes: str | None = Field(default=None, max_length=5000)


class EnquiryClose(BaseModel):
    """Close an enquiry with a required human-readable reason."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_and_validate_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Reason must contain at least 3 non-whitespace characters")
        return normalized


class EnquiryRead(BaseModel):
    """Safe enquiry representation; deliberately excludes idempotency_key."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int | None = None
    site_id: int | None = None
    contact_name: str
    phone_raw: str
    phone_e164: str | None = None
    email: str | None = None
    source: EnquirySource
    status: EnquiryStatus
    notes: str | None = None
    address_line: str
    city: str
    state: str
    pincode: str
    requested_capacity_kw: Decimal | None = None
    system_type: SystemType
    customer_type: CustomerType
    subsidy_requested: bool
    shadow_free_roof_area_sqft: Decimal | None = None
    monthly_bill_amount: Decimal | None = None
    grid_connection_suitable: bool | None = None
    assigned_to: int | None = None
    qualified_by: int | None = None
    qualified_at: datetime | None = None
    close_reason: str | None = None
    is_overdue: bool = False
    created_at: datetime
    updated_at: datetime


class EnquiryPublicReceipt(BaseModel):
    """Minimal confirmation returned after a public enquiry is accepted."""

    model_config = ConfigDict(extra="forbid")

    reference: str = Field(min_length=1, max_length=30)
    message: str = Field(min_length=1, max_length=300)
