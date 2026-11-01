"""Installation read response schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TechnicianAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    technician_id: int
    full_name: str
    hours_worked: Decimal
    hourly_rate: Decimal


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    evidence_type: str
    content_type: str
    file_size_bytes: int
    caption: str | None
    captured_at: datetime | None


class InstallationRead(BaseModel):
    id: int
    order_id: int
    order_number: str
    customer_id: int
    customer_name: str
    site_id: int
    site_name: str | None
    city: str
    status: str
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    completion_notes: str | None
    installed_capacity_kw: Decimal | None
    power_test_passed: bool | None
    signed_by_name: str | None
    signed_at: datetime | None
    technicians: list[TechnicianAssignmentRead]
    evidence: list[EvidenceRead]
