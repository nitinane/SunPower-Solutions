"""Printable GST invoices. Money goes out as strings (Decimal)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.core.enums import InvoiceKind, InvoiceStatus
from app.schemas.quotes import QuoteSite


class InvoiceSeller(BaseModel):
    name: str
    gstin: str
    address: str
    state: str


class InvoiceBuyer(BaseModel):
    customer_id: int
    name: str
    phone: str
    email: str | None = None
    gstin: str | None = None
    address: QuoteSite


class InvoiceLineRead(BaseModel):
    description: str
    sku: str | None = None
    qty: Decimal
    unit_price: Decimal
    gst_percent: Decimal
    taxable: Decimal
    gst_amount: Decimal


class InvoiceRead(BaseModel):
    id: int
    invoice_number: str
    kind: InvoiceKind
    status: InvoiceStatus
    financial_year: str
    invoice_date: date
    place_of_supply: str
    seller: InvoiceSeller
    buyer: InvoiceBuyer
    order_id: int | None = None
    order_number: str | None = None
    ticket_id: int | None = None
    ticket_number: str | None = None
    lines: list[InvoiceLineRead]
    taxable_amount: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    gst_total: Decimal
    total: Decimal
    amount_paid: Decimal | None = None   # orders only
    balance_due: Decimal | None = None   # orders only
    created_at: datetime


class InvoiceSummary(BaseModel):
    id: int
    invoice_number: str
    kind: InvoiceKind
    invoice_date: date
    customer_name: str
    order_id: int | None = None
    ticket_id: int | None = None
    taxable_amount: Decimal
    gst_total: Decimal
    total: Decimal
