"""Director summary and read-only share contracts."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Period = Literal["today", "week", "month"]
JobSort = Literal["recent", "profit_asc"]


class DashboardCards(BaseModel):
    new_enquiries: int
    orders_confirmed: int
    payments_received: Decimal
    advance_payments: Decimal
    technician_hours: Decimal
    profit: Decimal
    stock_purchases: Decimal
    unfinished_jobs: int
    open_repairs: int


class JobProfit(BaseModel):
    order_number: str
    customer: str
    system_kw: Decimal
    revenue: Decimal
    material_cost: Decimal
    labour_cost: Decimal
    warranty_service_cost: Decimal
    profit: Decimal
    margin_percent: Decimal


class UnfinishedJob(BaseModel):
    order_number: str
    customer: str
    stage: str
    days_open: int


class OpenRepair(BaseModel):
    ticket_number: str
    customer: str
    under_warranty: bool
    status: str
    days_open: int


class DashboardSummary(BaseModel):
    period: Period
    from_at: datetime
    to_at: datetime
    cards: DashboardCards
    profit_per_job: list[JobProfit]
    unfinished_jobs: list[UnfinishedJob]
    open_repairs: list[OpenRepair]


class DashboardTrendPoint(BaseModel):
    month: str
    booked_order_value: Decimal
    payments_received: Decimal


class ShareCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: Period
    expires_in_hours: int = Field(default=72, ge=1, le=168)


class ShareRead(BaseModel):
    id: int
    url: str
    expires_at: datetime


class ShareListItem(BaseModel):
    id: int
    period: Period
    expires_at: datetime
    created_at: datetime
