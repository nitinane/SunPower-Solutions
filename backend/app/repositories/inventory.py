"""Inventory queries with deterministic row locking."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import Inventory, SerializedUnit, StockMovement


def serial_by_number(db: Session, serial: str) -> SerializedUnit | None:
    return db.scalars(
        select(SerializedUnit)
        .where(SerializedUnit.serial_number == serial)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def lock_serials(db: Session, ids: list[int]) -> list[SerializedUnit]:
    return list(
        db.scalars(
            select(SerializedUnit)
            .where(SerializedUnit.id.in_(ids))
            .order_by(SerializedUnit.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


def lock_balances(db: Session, product_ids: list[int]) -> dict[int, Inventory]:
    rows = db.scalars(
        select(Inventory)
        .where(Inventory.product_id.in_(product_ids))
        .order_by(Inventory.product_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {row.product_id: row for row in rows}


def update(db: Session, row, **values) -> None:
    for key, value in values.items():
        setattr(row, key, value)
    db.flush()


def add_movement(db: Session, **values) -> StockMovement:
    row = StockMovement(**values)
    db.add(row)
    db.flush()
    return row
