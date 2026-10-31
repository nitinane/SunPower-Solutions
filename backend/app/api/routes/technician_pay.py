"""
Monthly technician pay runs (director) and the technician's own pay.
All rules live in app/services/technician_pay.py.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.technician_pay import (
    MONTH_PATTERN,
    MyPay,
    PayRunCreate,
    PayRunMarkPaid,
    PayRunRead,
    PayRunSummary,
)
from app.services import technician_pay as pay_service
from app.services.common import RequestMeta

router = APIRouter(tags=["technician pay"])

DbSession = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Director = Annotated[User, Depends(require_role(UserRole.DIRECTOR))]
Technician = Annotated[User, Depends(require_role(UserRole.TECHNICIAN))]
RunId = Annotated[int, Path(gt=0)]


@router.post(
    "/pay-runs",
    response_model=PayRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create or recalculate the draft pay run for a month",
)
def calculate(data: PayRunCreate, db: DbSession, actor: Director, meta: Meta,
              response: Response) -> PayRunRead:
    run, created = pay_service.calculate(db, data, actor=actor, meta=meta)
    if not created:
        response.status_code = status.HTTP_200_OK
    return pay_service.get_run(db, run.id)


@router.get("/pay-runs", response_model=Page[PayRunSummary], summary="Pay runs, newest first")
def list_runs(
    db: DbSession,
    actor: Director,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[PayRunSummary]:
    items, total = pay_service.list_runs(db, page=page, page_size=page_size)
    return Page[PayRunSummary](items=items, total=total, page=page, page_size=page_size)


@router.get("/pay-runs/{run_id}", response_model=PayRunRead, summary="Lines + breakdown")
def get_run(run_id: RunId, db: DbSession, actor: Director) -> PayRunRead:
    return pay_service.get_run(db, run_id)


@router.post("/pay-runs/{run_id}/mark-paid", response_model=PayRunRead, summary="Lock as paid")
def mark_paid(
    run_id: RunId, data: PayRunMarkPaid, db: DbSession, actor: Director, meta: Meta
) -> PayRunRead:
    run = pay_service.mark_paid(db, run_id, data, actor=actor, meta=meta)
    return pay_service.get_run(db, run.id)


@router.get("/me/pay", response_model=MyPay, summary="My pay for a month")
def my_pay(
    db: DbSession,
    actor: Technician,
    month: Annotated[str, Query(pattern=MONTH_PATTERN)],
) -> MyPay:
    return pay_service.my_pay(db, month, actor=actor)
