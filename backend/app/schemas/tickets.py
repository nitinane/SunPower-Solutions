"""Support search and repair ticket contracts."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ChargeType, TicketPriority, TicketStatus
from app.core.validators import OptionalText, PersonName
from app.schemas.auth import AuditEntryRead
from app.schemas.quotes import QuoteCustomer, QuoteSite


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: int = Field(gt=0)
    serialized_unit_id: int | None = Field(default=None, gt=0)
    order_item_id: int | None = Field(default=None, gt=0)
    fault_code: OptionalText = Field(max_length=60)
    issue_description: str = Field(min_length=1, max_length=5000)
    priority: TicketPriority = TicketPriority.NORMAL

    @model_validator(mode="after")
    def valid_target(self):
        if (self.serialized_unit_id is None) == (self.order_item_id is None):
            raise ValueError("Supply exactly one of serialized_unit_id or order_item_id")
        self.issue_description = self.issue_description.strip()
        if not self.issue_description:
            raise ValueError("Issue description is required")
        return self


class TicketAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    technician_id: int = Field(gt=0)
    visit_date: date


class PartUse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int = Field(gt=0)
    qty: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class TicketResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_notes: str = Field(min_length=1, max_length=5000)
    labour_hours: Decimal = Field(ge=0, max_digits=5, decimal_places=2)
    parts: list[PartUse] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_work(self):
        self.work_notes = self.work_notes.strip()
        if not self.work_notes:
            raise ValueError("Work notes are required")
        if len({part.product_id for part in self.parts}) != len(self.parts):
            raise ValueError("Combine duplicate products into one part line")
        return self


class TicketConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool
    customer_name: PersonName
    note: OptionalText = Field(default=None, max_length=5000)


class TicketChargeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    charge_type: ChargeType
    product_id: int | None
    description: str | None
    quantity: Decimal
    customer_price: Decimal
    cost_amount: Decimal
    covered_by_warranty: bool
    amount: Decimal


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ticket_number: str
    customer_id: int
    site_id: int
    faulty_serial_unit_id: int | None
    order_item_id: int | None
    warranty_id: int | None
    status: TicketStatus
    priority: TicketPriority
    fault_code: str | None
    issue_description: str
    under_warranty: bool
    coverage_label: str
    assigned_to: int | None
    visit_date: date | None
    work_notes: str | None
    labour_hours: Decimal | None
    parts_subtotal: Decimal
    labour_amount: Decimal
    gst: Decimal
    total: Decimal
    opened_at: datetime
    resolved_at: datetime | None
    confirmed_by_name: str | None
    customer_confirmed_at: datetime | None
    charges: list[TicketChargeRead]
    history: list[AuditEntryRead]


class SupportOrder(BaseModel):
    id: int
    number: str
    status: str


class SupportUnit(BaseModel):
    serialized_unit_id: int
    serial: str
    product: str
    warranty_end: date | None
    warranty_status: Literal["active", "expired"]
    days_left: int


class SupportTicketRef(BaseModel):
    id: int
    ticket_number: str
    status: TicketStatus


class SupportResult(BaseModel):
    customer: QuoteCustomer
    sites: list[QuoteSite]
    orders: list[SupportOrder]
    units: list[SupportUnit]
    open_tickets: list[SupportTicketRef]
