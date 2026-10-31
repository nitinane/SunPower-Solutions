"""Employee list for dropdowns, e.g. GET /users?role=surveyor&role=technician."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.users import UserBrief
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[Session, Depends(get_db)]
Staff = Annotated[
    User,
    Depends(require_role(
        UserRole.OFFICE, UserRole.MANAGER, UserRole.DIRECTOR, UserRole.SUPPORT, UserRole.WAREHOUSE
    )),
]


@router.get("", response_model=list[UserBrief], summary="Active employees (filter by role)")
def list_users(
    db: DbSession,
    actor: Staff,
    role: Annotated[list[UserRole] | None, Query()] = None,
) -> list[UserBrief]:
    users = user_service.list_active_users(db, role)
    return [UserBrief.model_validate(user) for user in users]
