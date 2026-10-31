"""Crew schedule, installation form, evidence. Money/kW/hours go out as strings (Decimal)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import (
    EvidenceType,
    InstallationJobStatus,
    SurveyStatus,
    TicketPriority,
    TicketStatus,
)
from app.schemas.quotes import QuoteSite

MAX_CREW = 6


class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_date: date
    technician_ids: list[int] = Field(min_length=1, max_length=MAX_CREW)

    @field_validator("technician_ids")
    @classmethod
    def unique_ids(cls, value: list[int]) -> list[int]:
        if any(i <= 0 for i in value):
            raise ValueError("Technician ids must be positive")
        return list(dict.fromkeys(value))


class JobComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_kw: Decimal = Field(ge=Decimal("0.5"), le=Decimal("50"), max_digits=8, decimal_places=2)
    power_test_passed: bool
    signer_name: str = Field(min_length=2, max_length=150)
    # 500 KB of PNG is ~683 KB of base64; leave room for a data: URL prefix.
    signature_png_base64: str = Field(min_length=1, max_length=700_000)

    @field_validator("signer_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Signer name must have at least 2 characters")
        return cleaned


class CrewMember(BaseModel):
    user_id: int
    name: str
    hours: Decimal | None = None


class InstalledLine(BaseModel):
    order_item_id: int
    sku: str
    name: str
    qty: Decimal
    requires_serial: bool
    serials: list[str]


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    kind: EvidenceType = Field(validation_alias="evidence_type")
    content_type: str
    size_bytes: int = Field(validation_alias="file_size_bytes")
    created_at: datetime


class JobRead(BaseModel):
    id: int
    status: InstallationJobStatus
    order_id: int
    order_number: str
    customer_name: str
    customer_phone: str
    site: QuoteSite
    scheduled_date: date | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    system_kw: Decimal | None = None
    power_test_passed: bool | None = None
    signer_name: str | None = None
    crew: list[CrewMember]
    lines: list[InstalledLine]
    photo_ids: list[int]
    signature_id: int | None = None


class ScheduleRow(BaseModel):
    job_id: int
    status: InstallationJobStatus
    scheduled_date: date | None = None
    order_id: int
    order_number: str
    customer_name: str
    customer_phone: str
    site: QuoteSite
    crew: list[CrewMember]


class TodaySurvey(BaseModel):
    id: int
    status: SurveyStatus
    scheduled_at: datetime | None = None
    customer_name: str
    site: QuoteSite


class TodayTicketVisit(BaseModel):
    id: int
    ticket_number: str
    status: TicketStatus
    priority: TicketPriority
    visit_date: date | None = None
    issue_description: str
    customer_name: str
    site: QuoteSite


class MyToday(BaseModel):
    date: date
    surveys: list[TodaySurvey]
    installation_jobs: list[ScheduleRow]
    ticket_visits: list[TodayTicketVisit]
