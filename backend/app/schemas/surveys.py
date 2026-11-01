"""Site survey requests and responses (PDF: technician measures direction, tilt, cable distance)."""

from datetime import datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.core.enums import RoofDirection, SurveyStatus
from app.core.validators import OptionalText


class SurveySchedule(BaseModel):
    """Office books a surveyor for a qualified enquiry."""

    model_config = ConfigDict(extra="forbid")

    surveyor_id: int = Field(gt=0)
    scheduled_at: AwareDatetime


class SurveySubmit(BaseModel):
    """What the surveyor measures on the roof."""

    model_config = ConfigDict(extra="forbid")

    roof_direction: RoofDirection
    roof_tilt_deg: Decimal = Field(ge=0, le=90, max_digits=5, decimal_places=2)
    cable_distance_m: Decimal = Field(gt=0, le=1000, max_digits=6, decimal_places=2)
    findings: OptionalText = Field(default=None, max_length=5000)


class SurveyReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Reason must have at least 3 characters")
        return cleaned


class SurveyRead(BaseModel):
    """Survey plus who/where to visit (filled from the enquiry by the service)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    enquiry_id: int
    site_id: int
    surveyor_id: int
    status: SurveyStatus
    scheduled_at: datetime | None = None
    submitted_at: datetime | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    roof_direction: RoofDirection | None = None
    roof_tilt_deg: Decimal | None = None
    cable_distance_m: Decimal | None = None
    findings: str | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    contact_name: str | None = None
    contact_phone: str | None = None
    address_line: str | None = None
    city: str | None = None
    pincode: str | None = None