"""Monthly technician pay runs. Money and hours go out as strings (Decimal)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PayoutStatus

MONTH_PATTERN = r"^[0-9]{4}-(0[1-9]|1[0-2])$"


class PayRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str = Field(pattern=MONTH_PATTERN, examples=["2026-11"])


class PayRunMarkPaid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paid_on: date
    payment_reference: str = Field(min_length=1, max_length=100)


class JobHours(BaseModel):
    job_id: int
    order_number: str
    hours: Decimal
    hourly_rate: Decimal
    amount: Decimal


class TicketHours(BaseModel):
    ticket_id: int
    ticket_number: str
    hours: Decimal


class PayLine(BaseModel):
    technician_id: int
    technician_name: str
    install_hours: Decimal
    repair_hours: Decimal
    rate: Decimal
    install_amount: Decimal
    repair_amount: Decimal
    amount: Decimal
    jobs: list[JobHours]
    tickets: list[TicketHours]


class PayRunSummary(BaseModel):
    id: int
    month: str
    status: PayoutStatus
    paid_on: date | None
    payment_reference: str | None
    technician_count: int
    total_amount: Decimal


class PayRunRead(PayRunSummary):
    lines: list[PayLine]


class MyPay(BaseModel):
    pay_run_id: int
    month: str
    status: PayoutStatus
    paid_on: date | None
    line: PayLine | None
