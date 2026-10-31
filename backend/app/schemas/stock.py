"""Stock receiving and on-hand contracts."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validators import SerialNumber


class ReceiptLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit_cost: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    serials: list[SerialNumber] | None = Field(default=None, max_length=1000)


class ReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_name: str = Field(min_length=1, max_length=180)
    supplier_invoice_ref: str = Field(min_length=1, max_length=100)
    received_on: date
    lines: list[ReceiptLineCreate] = Field(min_length=1, max_length=100)

    @field_validator("supplier_name", "supplier_invoice_ref")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Required")
        return value


class ReceiptLineRead(BaseModel):
    id: int
    product_id: int
    sku: str
    name: str
    qty: Decimal
    unit_cost: Decimal
    line_total: Decimal


class ReceiptRead(BaseModel):
    id: int
    receipt_number: str
    supplier_name: str
    supplier_invoice_ref: str
    received_on: date
    created_by: int | None
    created_at: datetime
    total: Decimal
    lines: list[ReceiptLineRead]


class StockRow(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
    requires_serial: bool
    on_hand: Decimal
    low_stock: bool
