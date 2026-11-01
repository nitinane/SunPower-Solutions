"""User (employee) queries. No commits and no business rules here."""

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.models.users import User


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    """Case-insensitive lookup; uses the unique index on lower(email)."""
    return db.scalars(select(User).where(func.lower(User.email) == email.strip().lower())).first()


def list_active(db: Session, roles: Iterable[UserRole] | None = None) -> list[User]:
    """Active users, optionally filtered by role (for 'assign to' dropdowns)."""
    stmt = select(User).where(User.is_active.is_(True))
    role_list = list(roles or [])
    if role_list:
        stmt = stmt.where(User.role.in_(role_list))
    return list(db.scalars(stmt.order_by(User.full_name)))


def create(db: Session, data: dict[str, Any]) -> User:
    user = User(**data)
    db.add(user)
    db.flush()
    return user