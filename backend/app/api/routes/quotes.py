"""
Quotes HTTP layer (office, director; admin always allowed).

Approved survey -> pick a package -> DRAFT quote -> send -> accept (creates the order) or reject.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import QuoteStatus, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.quotes import (
    QuoteAcceptResult,
    QuoteCreate,
    QuoteRead,
    QuoteReject,
    QuoteSummary,
)
from app.services import quotes as quote_service
from app.services.common import RequestMeta

router = APIRouter(prefix="/quotes", tags=["quotes"])

DbSession = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Sales = Annotated[User, Depends(require_role(UserRole.OFFICE, UserRole.DIRECTOR))]
QuoteId = Annotated[int, Path(gt=0)]


@router.post(
    "",
    response_model=QuoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft quote from a package for an approved survey",
)
def create_quote(data: QuoteCreate, db: DbSession, actor: Sales, meta: Meta) -> QuoteRead:
    quote = quote_service.create_quote(db, data, actor=actor, meta=meta)
    return quote_service.to_read(db, quote)


@router.get("", response_model=Page[QuoteSummary], summary="Quotes")
def list_quotes(
    db: DbSession,
    actor: Sales,
    status_filter: Annotated[QuoteStatus | None, Query(alias="status")] = None,
    enquiry_id: Annotated[int | None, Query(gt=0)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[QuoteSummary]:
    rows, total = quote_service.list_quotes(
        db, status=status_filter, enquiry_id=enquiry_id, page=page, page_size=page_size
    )
    return Page[QuoteSummary](
        items=[QuoteSummary.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{quote_id}", response_model=QuoteRead, summary="Printable quote")
def get_quote(quote_id: QuoteId, db: DbSession, actor: Sales) -> QuoteRead:
    return quote_service.to_read(db, quote_service.get_quote(db, quote_id))


@router.post("/{quote_id}/send", response_model=QuoteRead, summary="DRAFT -> SENT")
def send_quote(quote_id: QuoteId, db: DbSession, actor: Sales, meta: Meta) -> QuoteRead:
    quote = quote_service.send_quote(db, quote_id, actor=actor, meta=meta)
    return quote_service.to_read(db, quote)


@router.post(
    "/{quote_id}/accept",
    response_model=QuoteAcceptResult,
    summary="SENT -> ACCEPTED, creates the order (waiting for payment)",
)
def accept_quote(
    quote_id: QuoteId, db: DbSession, actor: Sales, meta: Meta
) -> QuoteAcceptResult:
    quote, order_id = quote_service.accept_quote(db, quote_id, actor=actor, meta=meta)
    return QuoteAcceptResult(quote=quote_service.to_read(db, quote), order_id=order_id)


@router.post("/{quote_id}/reject", response_model=QuoteRead, summary="SENT -> REJECTED")
def reject_quote(
    quote_id: QuoteId, data: QuoteReject, db: DbSession, actor: Sales, meta: Meta
) -> QuoteRead:
    quote = quote_service.reject_quote(db, quote_id, data, actor=actor, meta=meta)
    return quote_service.to_read(db, quote)
