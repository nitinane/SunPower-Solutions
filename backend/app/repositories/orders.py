"""Order and order line queries. No commits and no business rules here."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orders import Order, OrderItem


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
