"""Subsidy application + document checklist queries. No commits and no business rules here."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customers import Customer
from app.models.enquiries import Enquiry
from app.models.orders import Order
from app.models.quotes import Quote
from app.models.subsidies import SubsidyApplication, SubsidyDocument


def get(db: Session, application_id: int, *, lock: bool = False) -> SubsidyApplication | None:
    stmt = select(SubsidyApplication).where(SubsidyApplication.id == application_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalars(stmt).first()


def get_by_order(db: Session, order_id: int) -> SubsidyApplication | None:
    stmt = select(SubsidyApplication).where(SubsidyApplication.order_id == order_id)
    return db.scalars(stmt).first()


def get_by_application_number(db: Session, number: str) -> SubsidyApplication | None:
    stmt = select(SubsidyApplication).where(SubsidyApplication.application_number == number)
    return db.scalars(stmt).first()


def subsidy_requested(db: Session, order_id: int) -> bool:
    """Did the enquiry behind this order ask for a subsidy?"""
    stmt = (
        select(Enquiry.subsidy_requested)
        .join(Quote, Quote.enquiry_id == Enquiry.id)
        .join(Order, Order.quote_id == Quote.id)
        .where(Order.id == order_id)
    )
    return bool(db.scalar(stmt))


def create(db: Session, data: dict[str, Any], doc_types: list[str]) -> SubsidyApplication:
    application = SubsidyApplication(**data)
    db.add(application)
    db.flush()
    db.add_all(SubsidyDocument(application_id=application.id, doc_type=d) for d in doc_types)
    db.flush()
    return application


def update(db: Session, row: Any, data: dict[str, Any]) -> Any:
    for field, value in data.items():
        setattr(row, field, value)
    db.flush()
    return row


def list_documents(db: Session, application_id: int) -> list[SubsidyDocument]:
    stmt = (
        select(SubsidyDocument)
        .where(SubsidyDocument.application_id == application_id)
        .order_by(SubsidyDocument.id)
    )
    return list(db.scalars(stmt))


def get_document(
    db: Session, application_id: int, doc_type: str, *, lock: bool = False
) -> SubsidyDocument | None:
    stmt = select(SubsidyDocument).where(
        SubsidyDocument.application_id == application_id, SubsidyDocument.doc_type == doc_type
    )
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalars(stmt).first()


def order_and_customer(db: Session, order_id: int) -> tuple[str, str] | None:
    stmt = (
        select(Order.order_number, Customer.full_name)
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.id == order_id)
    )
    row = db.execute(stmt).first()
    return (row[0], row[1]) if row else None


def list_page(
    db: Session, *, status: str | None, limit: int, offset: int
) -> tuple[list[tuple[SubsidyApplication, str | None, str, int]], int]:
    """(application, order number, customer name, missing document count), newest first."""
    missing = (
        select(func.count(SubsidyDocument.id))
        .where(
            SubsidyDocument.application_id == SubsidyApplication.id,
            SubsidyDocument.received.is_(False),
        )
        .correlate(SubsidyApplication)
        .scalar_subquery()
    )
    base = select(SubsidyApplication)
    if status:
        base = base.where(SubsidyApplication.status == status)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    stmt = (
        select(SubsidyApplication, Order.order_number, Customer.full_name, missing)
        .join(Customer, Customer.id == SubsidyApplication.customer_id)
        .outerjoin(Order, Order.id == SubsidyApplication.order_id)
        .order_by(SubsidyApplication.created_at.desc(), SubsidyApplication.id.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        stmt = stmt.where(SubsidyApplication.status == status)
    return [tuple(row) for row in db.execute(stmt).all()], total
