"""Quote requests and printable quote responses. Money goes out as strings (Decimal)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import QuoteStatus
from app.core.validators import OptionalText
from app.schemas.catalog import PriceLine


class QuoteCreate(BaseModel):
    """Sales picks a package for an approved survey; the parts list fills in by itself."""

    model_config = ConfigDict(extra="forbid")

    survey_id: int = Field(gt=0)
    package_id: int = Field(gt=0)
    include_installation: bool = False
    notes: OptionalText = Field(default=None, max_length=5000)


class QuoteReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Reason must have at least 3 characters")
        return cleaned


class QuoteCustomer(BaseModel):
    id: int | None = None
    name: str
    phone: str | None = None
    email: str | None = None


class QuoteSite(BaseModel):
    id: int
    address_line1: str
    address_line2: str | None = None
    city: str
    state: str
    pincode: str


class QuoteSummary(BaseModel):
    """List row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    quote_number: str
    enquiry_id: int
    survey_id: int
    package_id: int | None = None
    status: QuoteStatus
    subtotal: Decimal
    gst: Decimal = Field(validation_alias="tax_total")
    total: Decimal
    created_at: datetime
    updated_at: datetime


class QuoteRead(BaseModel):
    """Printable quote."""

    id: int
    quote_number: str
    enquiry_id: int
    survey_id: int
    package_id: int | None = None
    status: QuoteStatus
    customer: QuoteCustomer
    site: QuoteSite
    lines: list[PriceLine]
    subtotal: Decimal
    gst: Decimal
    total: Decimal
    notes: str | None = None
    valid_until: date | None = None
    created_at: datetime
    updated_at: datetime


class QuoteAcceptResult(BaseModel):
    quote: QuoteRead
    order_id: int
