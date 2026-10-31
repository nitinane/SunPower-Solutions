"""Director dashboard and public read-only shares."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.dashboard import DashboardSummary, Period, ShareCreate, ShareRead
from app.services import dashboard as service
from app.services.common import RequestMeta

router = APIRouter(tags=["dashboard"])
Db = Annotated[Session, Depends(get_db)]
Director = Annotated[User, Depends(require_role(UserRole.DIRECTOR))]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]


@router.get("/dashboard/summary", response_model=DashboardSummary)
def summary(db: Db, actor: Director, period: Period = "month") -> DashboardSummary:
    return service.summary(db, period)


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
