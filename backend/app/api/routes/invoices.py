"""
GST invoices (office, director; admin always allowed). Read-only except the backfill:
invoices are created by delivery / paid-repair closure and never change afterwards.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import InvoiceKind, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.invoices import InvoiceRead, InvoiceSummary
from app.services import invoices as invoice_service
from app.services.common import RequestMeta

router = APIRouter(tags=["invoices"])

DbSession = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Accounts = Annotated[User, Depends(require_role(UserRole.OFFICE, UserRole.DIRECTOR))]


@router.get("/invoices", response_model=Page[InvoiceSummary], summary="Invoices")
def list_invoices(
    db: DbSession,
    actor: Accounts,
    kind: InvoiceKind | None = None,
    first: Annotated[date | None, Query(alias="from")] = None,
    last: Annotated[date | None, Query(alias="to")] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[InvoiceSummary]:
    items, total = invoice_service.list_invoices(
        db, kind=kind, first=first, last=last, search=search, page=page, page_size=page_size
    )
    return Page[InvoiceSummary](items=items, total=total, page=page, page_size=page_size)


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead, summary="Printable invoice")
def get_invoice(
    invoice_id: Annotated[int, Path(gt=0)], db: DbSession, actor: Accounts
) -> InvoiceRead:
    return invoice_service.to_read(db, invoice_service.get_invoice(db, invoice_id))


@router.post(
    "/orders/{order_id}/invoice",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create the invoice for a delivered order if it is missing",
)
def create_order_invoice(
    order_id: Annotated[int, Path(gt=0)],
    response: Response,
    db: DbSession,
    actor: Accounts,
    meta: Meta,
) -> InvoiceRead:
    invoice, created = invoice_service.create_for_order_now(db, order_id, actor=actor, meta=meta)
    if not created:
        response.status_code = status.HTTP_200_OK
    return invoice_service.to_read(db, invoice)
