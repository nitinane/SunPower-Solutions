"""Director dashboard and public read-only shares."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.dashboard import (
    DashboardSummary,
    DashboardTrendPoint,
    JobSort,
    Period,
    ShareCreate,
    ShareListItem,
    ShareRead,
)
from app.services import dashboard as service
from app.services.common import RequestMeta

router = APIRouter(tags=["dashboard"])
Db = Annotated[Session, Depends(get_db)]
Director = Annotated[User, Depends(require_role(UserRole.DIRECTOR))]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]


@router.get("/dashboard/summary", response_model=DashboardSummary)
def summary(
    db: Db, actor: Director, period: Period = "month", sort: JobSort = "recent"
) -> DashboardSummary:
    return service.summary(db, period, sort)


@router.get("/dashboard/trend", response_model=list[DashboardTrendPoint])
def trend(
    db: Db, actor: Director, months: Annotated[int, Query(ge=1, le=36)] = 12
) -> list[DashboardTrendPoint]:
    return service.trend(db, months)


@router.post("/dashboard/share", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
def create_share(data: ShareCreate, db: Db, actor: Director, meta: Meta) -> ShareRead:
    return service.create_share(db, data, actor=actor, meta=meta)


@router.delete("/dashboard/share/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(share_id: Annotated[int, Path(gt=0)], db: Db, actor: Director, meta: Meta) -> Response:
    service.revoke(db, share_id, actor=actor, meta=meta)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/public/dashboard/{token}", response_model=DashboardSummary)
def public_summary(token: str, db: Db) -> DashboardSummary:
    return service.public_summary(db, token)


@router.get("/dashboard/share", response_model=Page[ShareListItem])
def list_shares(
    db: Db, actor: Director,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ShareListItem]:
    items, total = service.list_shares(db, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)
