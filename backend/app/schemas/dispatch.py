"""Warehouse queue, scanner input and delivery responses."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.core.enums import DispatchStatus
from app.core.validators import PersonName, normalize_serial
from app.schemas.quotes import QuoteCustomer, QuoteSite


class ScanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    serial: str

    @field_validator("serial")
    @classmethod
    def clean_serial(cls, value: str) -> str:
        return normalize_serial(value)


class DeliveryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receiver_name: PersonName
    delivered_at: AwareDatetime | None = None


class ScannedSerial(BaseModel):
    dispatch_item_id: int
    serialized_unit_id: int
    serial: str


class DispatchLine(BaseModel):
    order_item_id: int
    sku: str
    name: str
    qty: Decimal
    requires_serial: bool
    scanned: int
    serials: list[ScannedSerial]


class DispatchRead(BaseModel):
    id: int
    dispatch_number: str
    order_id: int
    order_number: str
    customer: QuoteCustomer
    site: QuoteSite
    status: DispatchStatus
    lines: list[DispatchLine]
    dispatched_at: datetime | None
    delivered_at: datetime | None
    receiver_name: str | None
    created_at: datetime


class WarrantyRead(BaseModel):
    product_name: str
    serial: str | None
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    order_item_id: int
    product_id: int
    serialized_unit_id: int | None
    quantity: Decimal
    start_date: date
    end_date: date


class DeliveryRead(DispatchRead):
    warranties_created: int = Field(ge=0)
    warranties: list[WarrantyRead]
