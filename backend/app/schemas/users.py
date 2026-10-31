"""Employee data the frontend may see (never email/password hash in lists)."""

from pydantic import BaseModel, ConfigDict

from app.core.enums import UserRole


class UserBrief(BaseModel):
    """Small user card for dropdowns ('assign to', 'book surveyor') and name lookups."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: UserRole
    phone: str | None = None