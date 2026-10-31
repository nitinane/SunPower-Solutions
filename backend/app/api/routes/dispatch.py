"""Warehouse dispatch endpoints; all workflow rules are in the service."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import DispatchStatus, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.dispatch import (
    DeliveryCreate,
    DeliveryRead,
    DispatchRead,
    ScanCreate,
)
from app.services import dispatch as dispatch_service
from app.services import warranties as warranty_service
from app.services.common import RequestMeta

router = APIRouter(prefix="/dispatches", tags=["dispatch"])
Db = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(require_role(UserRole.WAREHOUSE, UserRole.DIRECTOR))]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
DispatchId = Annotated[int, Path(gt=0)]


@router.get("", response_model=Page[DispatchRead])
def list_dispatches(
    db: Db,
    actor: Actor,
    status_filter: Annotated[DispatchStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[DispatchRead]:
    items, total = dispatch_service.list_dispatches(
        db, status=status_filter, page=page, page_size=page_size
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{dispatch_id}", response_model=DispatchRead)
def get_dispatch(dispatch_id: DispatchId, db: Db, actor: Actor) -> DispatchRead:
    return dispatch_service.to_read(db, dispatch_service.get_dispatch(db, dispatch_id))


@router.post("/{dispatch_id}/scan", response_model=DispatchRead)
def scan(
    dispatch_id: DispatchId, data: ScanCreate, db: Db, actor: Actor, meta: Meta
) -> DispatchRead:
    dispatch = dispatch_service.scan(db, dispatch_id, data.serial, actor=actor, meta=meta)
    return dispatch_service.to_read(db, dispatch)


@router.delete("/{dispatch_id}/scan/{dispatch_item_id}", response_model=DispatchRead)
def unscan(
    dispatch_id: DispatchId,
    dispatch_item_id: Annotated[int, Path(gt=0)],
    db: Db,
    actor: Actor,
    meta: Meta,
) -> DispatchRead:
    dispatch = dispatch_service.unscan(db, dispatch_id, dispatch_item_id, actor=actor, meta=meta)
    return dispatch_service.to_read(db, dispatch)


@router.post("/{dispatch_id}/send", response_model=DispatchRead)
def send(dispatch_id: DispatchId, db: Db, actor: Actor, meta: Meta) -> DispatchRead:
    dispatch = dispatch_service.send(db, dispatch_id, actor=actor, meta=meta)
    return dispatch_service.to_read(db, dispatch)


@router.post("/{dispatch_id}/deliver", response_model=DeliveryRead)
def deliver(
    dispatch_id: DispatchId, data: DeliveryCreate, db: Db, actor: Actor, meta: Meta
) -> DeliveryRead:
    dispatch, warranties = dispatch_service.deliver(db, dispatch_id, data, actor=actor, meta=meta)
    return DeliveryRead(
        **dispatch_service.to_read(db, dispatch).model_dump(),
        warranties_created=len(warranties),
        warranties=warranty_service.delivery_reads(db, dispatch, warranties),
    )
