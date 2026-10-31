"""Stock receiving from suppliers and on-hand stock."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.stock import ReceiptCreate, ReceiptRead, StockRow
from app.services import stock as service
from app.services.common import RequestMeta

router = APIRouter(prefix="/stock", tags=["stock"])
Db = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Receiver = Annotated[User, Depends(require_role(UserRole.WAREHOUSE, UserRole.DIRECTOR))]
StockViewer = Annotated[
    User, Depends(require_role(UserRole.WAREHOUSE, UserRole.OFFICE, UserRole.DIRECTOR))
]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.post("/receipts", response_model=ReceiptRead, status_code=status.HTTP_201_CREATED)
def create_receipt(data: ReceiptCreate, db: Db, actor: Receiver, meta: Meta) -> ReceiptRead:
    return service.to_read(db, service.create_receipt(db, data, actor=actor, meta=meta))


@router.get("/receipts", response_model=Page[ReceiptRead])
def list_receipts(
    db: Db,
    actor: Receiver,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    page: PageNo = 1,
    page_size: PageSize = 20,
) -> Page[ReceiptRead]:
    items, total = service.list_receipts(
        db, date_from=date_from, date_to=date_to, page=page, page_size=page_size
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/receipts/{receipt_id}", response_model=ReceiptRead)
def get_receipt(
    receipt_id: Annotated[int, Path(gt=0)], db: Db, actor: Receiver
) -> ReceiptRead:
    return service.to_read(db, service.get_receipt(db, receipt_id))


@router.get("", response_model=Page[StockRow])
def stock(db: Db, actor: StockViewer, page: PageNo = 1, page_size: PageSize = 50) -> Page[StockRow]:
    items, total = service.stock(db, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)
