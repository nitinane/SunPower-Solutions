"""Permission-scoped reports backed by PostgreSQL."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.cache import get_or_load
from app.core.deps import get_db, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.dashboard import ReportRead
from app.services.dashboard import build_report

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
Db = Annotated[Session, Depends(get_db)]
Director = Annotated[User, Depends(require_role(UserRole.ADMIN, UserRole.DIRECTOR))]


@router.get("/reports", response_model=ReportRead)
def get_report(db: Db, actor: Director) -> ReportRead:
    permission_scope = f"{actor.role}:{actor.id}"
    payload = get_or_load(
        "financial_report",
        permission_scope,
        "operations:all-time",
        lambda: build_report(db).model_dump(mode="python"),
    )
    return ReportRead.model_validate(payload)


@router.get("/summary", response_model=ReportRead)
def get_summary(db: Db, actor: Director) -> ReportRead:
    permission_scope = f"{actor.role}:{actor.id}"
    payload = get_or_load(
        "dashboard_summary",
        permission_scope,
        "operations:all-time",
        lambda: build_report(db).model_dump(mode="python"),
    )
    return ReportRead.model_validate(payload)
