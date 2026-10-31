"""Login request and the logged-in user returned to the frontend."""

from datetime import datetime

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