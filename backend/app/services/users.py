"""Employee lookups for dropdowns. Read-only for now (users are created by the seed script)."""

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.models.users import User
from app.repositories import users as user_repo


def list_active_users(db: Session, roles: Iterable[UserRole] | None = None) -> list[User]:
    """Active employees, optionally only some roles, sorted by name."""
    return user_repo.list_active(db, roles)