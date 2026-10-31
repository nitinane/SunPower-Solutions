"""Dispatch queries; transactions belong to services."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import DispatchStatus
from app.models.catalog import Product
from app.models.dispatch import Dispatch, DispatchItem
from app.models.inventory import SerializedUnit
from app.models.orders import OrderItem


def get_by_id(db: Session, dispatch_id: int, *, lock: bool = False) -> Dispatch | None:
    stmt = select(Dispatch).where(Dispatch.id == dispatch_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalars(stmt).first()


def list_page(db: Session, *, status: DispatchStatus | None, limit: int, offset: int):
    stmt = select(Dispatch)
    if status is not None:
        stmt = stmt.where(Dispatch.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Dispatch.created_at, Dispatch.id).limit(limit).offset(offset))
    return list(rows), total


def lines(db: Session, order_id: int):
    return db.execute(
        select(OrderItem, Product)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == order_id)
        .order_by(OrderItem.id)
    ).all()


def product_for_serial(db: Session, product_id: int) -> Product:
    return db.get(Product, product_id)


def scanned_items(db: Session, dispatch_id: int):
    return db.execute(
        select(DispatchItem, SerializedUnit)
        .join(SerializedUnit, SerializedUnit.id == DispatchItem.serialized_unit_id)
        .where(DispatchItem.dispatch_id == dispatch_id)
        .order_by(DispatchItem.id)
    ).all()


def add_item(db: Session, **values) -> DispatchItem:
    item = DispatchItem(**values)
    db.add(item)
    db.flush()
    return item


def delete_item(db: Session, item: DispatchItem) -> None:
    db.delete(item)
    db.flush()


def update(db: Session, dispatch: Dispatch, **values) -> None:
    for key, value in values.items():
        setattr(dispatch, key, value)
    db.flush()
