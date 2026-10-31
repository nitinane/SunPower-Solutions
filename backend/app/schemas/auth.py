"""Login request, the logged-in user, and history (audit) entries for the frontend."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import UserRole
from app.core.validators import RequiredEmail


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: RequiredEmail
    password: str = Field(min_length=1, max_length=128)


class CurrentUser(BaseModel):
    """Safe user data for the frontend. Never includes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: str | None = None
    role: UserRole


class LoginResponse(BaseModel):
    user: CurrentUser
    expires_at: datetime


class AuditEntryRead(BaseModel):
    """One line of a record's history (the 'chatter' timeline)."""

    id: int
    action: str
    actor_user_id: int | None = None
    actor_name: str | None = None
    old_data: dict[str, Any] | None = None
    new_data: dict[str, Any] | None = None
    created_at: datetime