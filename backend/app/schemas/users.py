"""Safe user profile response fields."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    full_name: str
    email: str
    phone: str | None
    role: str
    hourly_rate: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
