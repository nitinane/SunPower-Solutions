"""The logged-in technician's own day."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.installations import MyToday
from app.services import schedule as schedule_service

router = APIRouter(prefix="/me", tags=["me"])

DbSession = Annotated[Session, Depends(get_db)]
Technician = Annotated[User, Depends(require_role(UserRole.TECHNICIAN))]


@router.get("/today", response_model=MyToday, summary="My surveys, installations and visits today")
def today(db: DbSession, actor: Technician) -> MyToday:
    return schedule_service.my_today(db, actor=actor)
