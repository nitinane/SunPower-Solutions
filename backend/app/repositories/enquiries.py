"""Enquiries repositorie stub. TODO: implement with the owning team."""
"""
Enquiry queries. No commits and no business rules here (those live in services/enquiries.py).

All values are passed as bound parameters, so user input (e.g. search text) can never be
executed as SQL.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import EnquirySource, EnquiryStatus
from app.models.enquiries import Enquiry

OPEN_STATUSES = (EnquiryStatus.NEW, EnquiryStatus.CONTACTED, EnquiryStatus.QUALIFIED)
MIN_PHONE_DIGITS_FOR_SEARCH = 4


def get_by_id(db: Session, enquiry_id: int) -> Enquiry | None:
    return db.get(Enquiry, enquiry_id)


def get_by_id_for_update(db: Session, enquiry_id: int) -> Enquiry | None:
    """SELECT ... FOR UPDATE: locks the row until the service commits or rolls back."""
    stmt = (
        select(Enquiry)
        .where(Enquiry.id == enquiry_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).first()


def get_by_idempotency_key(db: Session, key: str) -> Enquiry | None:
    return db.scalars(select(Enquiry).where(Enquiry.idempotency_key == key)).first()


def find_open_by_phone(db: Session, phone_e164: str) -> Enquiry | None:
    """Newest enquiry for this phone that is still new, contacted or qualified."""
    stmt = (
        select(Enquiry)
        .where(Enquiry.phone_e164 == phone_e164, Enquiry.status.in_(OPEN_STATUSES))
        .order_by(Enquiry.created_at.desc(), Enquiry.id.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def create(db: Session, data: dict[str, Any]) -> Enquiry:
    """Insert and flush (so the id exists). The service decides when to commit."""
    enquiry = Enquiry(**data)
    db.add(enquiry)
    db.flush()
    return enquiry


def update(db: Session, enquiry: Enquiry, data: dict[str, Any]) -> Enquiry:
    for field, value in data.items():
        setattr(enquiry, field, value)
    db.flush()
    return enquiry


def list_page(
    db: Session,
    *,
    status: EnquiryStatus | None = None,
    source: EnquirySource | None = None,
    assigned_to: int | None = None,
    unassigned: bool = False,
    created_before: datetime | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Enquiry], int]:
    """Filtered, newest-first page plus the total count for the same filters."""
    stmt: Select[tuple[Enquiry]] = select(Enquiry)
    conditions = []
    if status:
        conditions.append(Enquiry.status == status)
    if source:
        conditions.append(Enquiry.source == source)
    if assigned_to is not None:
        conditions.append(Enquiry.assigned_to == assigned_to)
    if unassigned:
        conditions.append(Enquiry.assigned_to.is_(None))
    if created_before is not None:
        conditions.append(Enquiry.created_at <= created_before)
    if search:
        conditions.append(_search_condition(search))
    if conditions:
        stmt = stmt.where(*conditions)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Enquiry.created_at.desc(), Enquiry.id.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total


def _search_condition(search: str):
    """Match the name (case-insensitive) or, if 4+ digits were typed, the phone number."""
    pattern = f"%{_escape_like(search)}%"
    options = [Enquiry.contact_name.ilike(pattern, escape="\\")]
    digits = "".join(ch for ch in search if ch.isdigit())
    if len(digits) >= MIN_PHONE_DIGITS_FOR_SEARCH:
        options.append(Enquiry.phone_e164.contains(digits))
    return or_(*options)


def _escape_like(text: str) -> str:
    """Treat % and _ typed by the user as normal characters, not wildcards."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")