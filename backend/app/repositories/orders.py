"""Order and order line queries. No commits and no business rules here."""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import OrderStatus, PaymentStatus
from app.models.catalog import Product
from app.models.customers import Customer
from app.models.dispatch import Dispatch
from app.models.installations import InstallationJob
from app.models.orders import Order, OrderItem
from app.models.payments import Payment
from app.models.quotes import Quote

MIN_PHONE_DIGITS_FOR_SEARCH = 4


def get_by_quote_id(db: Session, quote_id: int) -> Order | None:
    return db.scalars(select(Order).where(Order.quote_id == quote_id)).first()


def create(db: Session, data: dict[str, Any]) -> Order:
    order = Order(**data)
    db.add(order)
    db.flush()
    return order


def update(db: Session, order: Order, data: dict[str, Any]) -> Order:
    for field, value in data.items():
        setattr(order, field, value)
    db.flush()
    return order


def add_item(db: Session, data: dict[str, Any]) -> OrderItem:
    item = OrderItem(**data)
    db.add(item)
    db.flush()
    return item


def list_items(db: Session, order_id: int) -> list[OrderItem]:
    stmt = select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
    return list(db.scalars(stmt))


def get_by_id(db: Session, order_id: int) -> Order | None:
    return db.get(Order, order_id)


def get_by_id_for_update(db: Session, order_id: int) -> Order | None:
    """SELECT ... FOR UPDATE: locks the order until the service commits or rolls back."""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).first()


def list_items_with_serial_flag(db: Session, order_id: int) -> list[tuple[OrderItem, bool]]:
    """Order lines plus products.tracks_serial (the spec's requires_serial)."""
    stmt = (
        select(OrderItem, Product.tracks_serial)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id)
    )
    return [(item, bool(flag)) for item, flag in db.execute(stmt).all()]


def _paid_subquery():
    return (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.order_id == Order.id, Payment.status == PaymentStatus.COMPLETED)
        .correlate(Order)
        .scalar_subquery()
    )


def list_page(
    db: Session,
    *,
    status: OrderStatus | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[tuple[Order, Customer, Decimal, Decimal]], int]:
    """Newest first. Rows: (order, customer, quote total, amount paid via SQL SUM)."""
    stmt = (
        select(Order, Customer, Quote.total, _paid_subquery())
        .join(Customer, Customer.id == Order.customer_id)
        .join(Quote, Quote.id == Order.quote_id)
    )
    if status:
        stmt = stmt.where(Order.status == status)
    if search:
        pattern = f"%{_escape_like(search)}%"
        options = [
            Order.order_number.ilike(pattern, escape="\\"),
            Customer.full_name.ilike(pattern, escape="\\"),
        ]
        digits = "".join(ch for ch in search if ch.isdigit())
        if len(digits) >= MIN_PHONE_DIGITS_FOR_SEARCH:
            options.append(Customer.phone_e164.contains(digits))
        stmt = stmt.where(or_(*options))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit).offset(offset)
    ).all()
    return [tuple(row) for row in rows], total


# ---------------------------------------------------------------- Pick list + crew job

def get_pick_list(db: Session, order_id: int) -> Dispatch | None:
    return db.scalars(select(Dispatch).where(Dispatch.order_id == order_id)).first()


def create_pick_list(db: Session, data: dict[str, Any]) -> Dispatch:
    dispatch = Dispatch(**data)
    db.add(dispatch)
    db.flush()
    return dispatch


def update_pick_list(db: Session, dispatch: Dispatch, data: dict[str, Any]) -> Dispatch:
    for field, value in data.items():
        setattr(dispatch, field, value)
    db.flush()
    return dispatch


def get_installation_job(db: Session, order_id: int) -> InstallationJob | None:
    return db.scalars(
        select(InstallationJob).where(InstallationJob.order_id == order_id)
    ).first()


def create_installation_job(db: Session, data: dict[str, Any]) -> InstallationJob:
    job = InstallationJob(**data)
    db.add(job)
    db.flush()
    return job


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
