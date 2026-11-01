"""Invoice and invoice-number queries. No commits and no business rules here."""

from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.enums import InvoiceKind
from app.models.customers import Customer
from app.models.invoices import Invoice, InvoiceItem, InvoiceSequence

MIN_PHONE_DIGITS_FOR_SEARCH = 4


def next_number(db: Session, financial_year: str) -> int:
    """Next gapless number for the year. Locks the year's row until the caller commits."""
    db.execute(
        insert(InvoiceSequence)
        .values(financial_year=financial_year, last_number=0)
        .on_conflict_do_nothing(index_elements=["financial_year"])
    )
    sequence = db.scalars(
        select(InvoiceSequence)
        .where(InvoiceSequence.financial_year == financial_year)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()
    sequence.last_number += 1
    db.flush()
    return sequence.last_number


def get(db: Session, invoice_id: int) -> Invoice | None:
    return db.get(Invoice, invoice_id)


def get_by_order(db: Session, order_id: int) -> Invoice | None:
    return db.scalars(select(Invoice).where(Invoice.order_id == order_id)).first()


def get_by_ticket(db: Session, ticket_id: int) -> Invoice | None:
    return db.scalars(select(Invoice).where(Invoice.ticket_id == ticket_id)).first()


def create(db: Session, data: dict[str, Any]) -> Invoice:
    invoice = Invoice(**data)
    db.add(invoice)
    db.flush()
    return invoice


def add_lines(db: Session, invoice_id: int, lines: list[dict[str, Any]]) -> None:
    db.add_all(InvoiceItem(invoice_id=invoice_id, **line) for line in lines)
    db.flush()


def list_lines(db: Session, invoice_id: int) -> list[InvoiceItem]:
    stmt = select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id).order_by(InvoiceItem.id)
    return list(db.scalars(stmt))


def list_page(
    db: Session,
    *,
    kind: InvoiceKind | None = None,
    first: date | None = None,
    last: date | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[tuple[Invoice, Customer]], int]:
    """Newest first. Search: invoice number, customer name, or 4+ phone digits."""
    stmt = select(Invoice, Customer).join(Customer, Customer.id == Invoice.customer_id)
    if kind:
        stmt = stmt.where(Invoice.kind == kind)
    if first:
        stmt = stmt.where(Invoice.issued_on >= first)
    if last:
        stmt = stmt.where(Invoice.issued_on <= last)
    if search:
        pattern = f"%{_escape_like(search)}%"
        options = [
            Invoice.invoice_number.ilike(pattern, escape="\\"),
            Customer.full_name.ilike(pattern, escape="\\"),
        ]
        digits = "".join(ch for ch in search if ch.isdigit())
        if len(digits) >= MIN_PHONE_DIGITS_FOR_SEARCH:
            options.append(Customer.phone_e164.contains(digits))
        stmt = stmt.where(or_(*options))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Invoice.issued_on.desc(), Invoice.id.desc()).limit(limit).offset(offset)
    ).all()
    return [tuple(row) for row in rows], total


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
