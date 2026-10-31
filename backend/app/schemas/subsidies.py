"""Subsidy tracking. Money goes out as strings (Decimal). Dates are IST business dates."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import SubsidyDocType, SubsidyStatus


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received: bool


class SubsidyAdvance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_status: SubsidyStatus
    date: date
    application_number: str | None = Field(default=None, max_length=100)
    amount: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("application_number", "reason")
    @classmethod
    def blank_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class SubsidyDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc_type: SubsidyDocType
    received: bool
    received_on: date | None
    has_file: bool


class SubsidyListItem(BaseModel):
    id: int
    order_id: int | None
    order_number: str | None
    customer_name: str
    status: SubsidyStatus
    application_number: str | None
    missing_document_count: int
    days_in_status: int


class SubsidyRead(BaseModel):
    id: int
    order_id: int | None
    order_number: str | None
    customer_name: str
    status: SubsidyStatus
    application_number: str | None
    applied_on: date | None
    inspected_on: date | None
    sanctioned_amount: Decimal | None
    sanctioned_on: date | None
    disbursed_amount: Decimal | None
    disbursed_on: date | None
    rejection_reason: str | None
    notes: str | None
    documents: list[SubsidyDocumentRead]
    missing_documents: list[SubsidyDocType]
    days_in_status: int
    created_at: datetime
