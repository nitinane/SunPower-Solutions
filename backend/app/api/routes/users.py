"""Current profile and authorized staff directory reads."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_role
from app.core.enums import UserRole
from app.exceptions import NotFound
from app.models.users import User
from app.schemas.users import UserRead

router = APIRouter(prefix="/users", tags=["users"])
Db = Annotated[Session, Depends(get_db)]
Current = Annotated[User, Depends(get_current_user)]
Admin = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.DIRECTOR))]


@router.get("/me", response_model=UserRead)
def get_me(actor: Current) -> UserRead:
    return UserRead.model_validate(actor)


@router.get("", response_model=list[UserRead])
def list_users(db: Db, _actor: Admin, role: UserRole | None = None) -> list[UserRead]:
    stmt = select(User).order_by(User.full_name)
    if role is not None:
        stmt = stmt.where(User.role == role)
    return [UserRead.model_validate(user) for user in db.scalars(stmt)]


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: Annotated[int, Path(gt=0)], db: Db, _actor: Admin) -> UserRead:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("User not found")
    return UserRead.model_validate(user)
