"""Orders and payments. Money goes out as strings (Decimal)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import (
    DispatchStatus,
    InstallationJobStatus,
    OrderStatus,
    PaymentMethod,
    PaymentType,
)
from app.schemas.quotes import QuoteCustomer, QuoteSite


class PaymentCreate(BaseModel):
    """Office records money received. The server decides advance / full / balance."""

    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=Decimal("0"), max_digits=12, decimal_places=2)
    method: PaymentMethod
    reference: str | None = Field(default=None, max_length=120)
    paid_at: datetime | None = None

    @field_validator("reference")
    @classmethod
    def strip_reference(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    amount: Decimal
    kind: PaymentType = Field(validation_alias="payment_type")
    method: PaymentMethod
    reference: str | None = Field(default=None, validation_alias="reference_number")
    paid_at: datetime | None = None
    received_by: int | None = Field(default=None, validation_alias="recorded_by")
    created_at: datetime


class OrderLine(BaseModel):
    id: int
    product_id: int
    sku: str
    name: str
    qty: Decimal
    unit_price: Decimal
    line_total: Decimal
    requires_serial: bool


class PickListRef(BaseModel):
    id: int
    status: DispatchStatus


class InstallationJobRef(BaseModel):
    id: int
    status: InstallationJobStatus
    scheduled_date: date | None = None


class OrderRead(BaseModel):
    id: int
    order_number: str
    quote_id: int
    status: OrderStatus
    customer: QuoteCustomer
    site: QuoteSite
    items: list[OrderLine]
    subtotal: Decimal
    gst: Decimal
    total: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    payments: list[PaymentRead]
    pick_list: PickListRef | None = None
    installation_job: InstallationJobRef | None = None
    confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OrderSummary(BaseModel):
    """List row."""

    id: int
    order_number: str
    status: OrderStatus
    customer_name: str
    customer_phone: str
    total: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    created_at: datetime


class PaymentResult(BaseModel):
    payment: PaymentRead
    order: OrderRead
