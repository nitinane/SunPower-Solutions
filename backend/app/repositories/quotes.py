"""Quote and quote line queries. No commits and no business rules here."""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.enums import QuoteStatus
from app.models.quotes import Quote, QuoteItem


def get_by_id(db: Session, quote_id: int) -> Quote | None:
    return db.get(Quote, quote_id)


def get_by_id_for_update(db: Session, quote_id: int) -> Quote | None:
    """SELECT ... FOR UPDATE: locks the row until the service commits or rolls back."""
    stmt = (
        select(Quote)
        .where(Quote.id == quote_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).first()


def create(db: Session, data: dict[str, Any]) -> Quote:
    quote = Quote(**data)
    db.add(quote)
    db.flush()
    return quote


def update(db: Session, quote: Quote, data: dict[str, Any]) -> Quote:
    for field, value in data.items():
        setattr(quote, field, value)
    db.flush()
    return quote


def add_item(db: Session, data: dict[str, Any]) -> QuoteItem:
    item = QuoteItem(**data)
    db.add(item)
    db.flush()
    return item


def list_items(db: Session, quote_id: int) -> list[QuoteItem]:
    stmt = select(QuoteItem).where(QuoteItem.quote_id == quote_id).order_by(QuoteItem.id)
    return list(db.scalars(stmt))


def list_open_for_enquiry_for_update(
    db: Session, enquiry_id: int, *, exclude_id: int
) -> list[Quote]:
    """Other draft/sent quotes of the same enquiry, locked."""
    stmt = (
        select(Quote)
        .where(
            Quote.enquiry_id == enquiry_id,
            Quote.id != exclude_id,
            Quote.status.in_((QuoteStatus.DRAFT, QuoteStatus.SENT)),
        )
        .order_by(Quote.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return list(db.scalars(stmt))


def list_page(
    db: Session,
    *,
    status: QuoteStatus | None = None,
    enquiry_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Quote], int]:
    stmt: Select[tuple[Quote]] = select(Quote)
    if status:
        stmt = stmt.where(Quote.status == status)
    if enquiry_id is not None:
        stmt = stmt.where(Quote.enquiry_id == enquiry_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.order_by(Quote.created_at.desc(), Quote.id.desc())
    rows = db.scalars(stmt.limit(limit).offset(offset))
    return list(rows), total
