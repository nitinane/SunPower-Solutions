"""Read-only inventory, movement, serialized unit, and dispatch APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.enums import UserRole
from app.exceptions import NotFound
from app.models.catalog import Product
from app.models.dispatch import Dispatch, DispatchItem
from app.models.inventory import Inventory, SerializedUnit, StockMovement
from app.models.users import User
from app.schemas.inventory import (
    DispatchItemRead,
    DispatchListItem,
    DispatchRead,
    InventoryProductRead,
    SerializedUnitRead,
    StockMovementRead,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])
Db = Annotated[Session, Depends(get_db)]
Staff = Annotated[
    User, Depends(require_role(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.WAREHOUSE))
]


@router.get("", response_model=list[InventoryProductRead])
def list_inventory(
    db: Db,
    _actor: Staff,
    low_stock: bool = False,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> list[InventoryProductRead]:
    stmt = (
        select(Product, Inventory)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.is_active.is_(True))
    )
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%"))
    rows = db.execute(stmt.order_by(Product.name)).all()
    result = []
    for product, stock in rows:
        available = stock.quantity_on_hand - stock.quantity_reserved
        if low_stock and available > 0:
            continue
        result.append(
            InventoryProductRead(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                category=product.category,
                cost_price=product.cost_price,
                sale_price=product.sale_price,
                quantity_on_hand=stock.quantity_on_hand,
                quantity_reserved=stock.quantity_reserved,
                quantity_available=available,
                low_stock=available <= 0,
            )
        )
    return result


@router.get("/movements", response_model=list[StockMovementRead])
def list_movements(
    db: Db,
    _actor: Staff,
    product_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[StockMovementRead]:
    stmt = select(StockMovement, Product.name).join(Product, Product.id == StockMovement.product_id)
    if product_id:
        stmt = stmt.where(StockMovement.product_id == product_id)
    return [
        StockMovementRead(
            id=m.id,
            product_id=m.product_id,
            product_name=name,
            order_id=m.order_id,
            quantity_delta=m.quantity_delta,
            reason=m.reason,
            note=m.note,
            created_at=m.created_at,
        )
        for m, name in db.execute(stmt.order_by(StockMovement.created_at.desc()).limit(limit))
    ]


@router.get("/serialized-units/{serial_number}", response_model=SerializedUnitRead)
def get_serialized_unit(serial_number: str, db: Db, _actor: Staff) -> SerializedUnitRead:
    row = db.execute(
        select(SerializedUnit, Product.name)
        .join(Product, Product.id == SerializedUnit.product_id)
        .where(SerializedUnit.serial_number == serial_number.strip().upper())
    ).first()
    if row is None:
        raise NotFound("Serialized unit not found")
    unit, name = row
    return SerializedUnitRead(
        id=unit.id,
        product_id=unit.product_id,
        product_name=name,
        serial_number=unit.serial_number,
        status=unit.status,
        received_at=unit.received_at,
    )


@router.get("/dispatches", response_model=list[DispatchListItem])
def list_dispatches(
    db: Db, _actor: Staff, limit: Annotated[int, Query(ge=1, le=200)] = 100
) -> list[DispatchListItem]:
    return [
        DispatchListItem.model_validate(row)
        for row in db.scalars(select(Dispatch).order_by(Dispatch.created_at.desc()).limit(limit))
    ]


@router.get("/dispatches/{dispatch_id}", response_model=DispatchRead)
def get_dispatch(dispatch_id: Annotated[int, Path(gt=0)], db: Db, _actor: Staff) -> DispatchRead:
    dispatch = db.get(Dispatch, dispatch_id)
    if dispatch is None:
        raise NotFound("Dispatch not found")
    items = db.execute(
        select(DispatchItem, Product.name)
        .join(Product, Product.id == DispatchItem.product_id)
        .where(DispatchItem.dispatch_id == dispatch_id)
        .order_by(DispatchItem.id)
    ).all()
    return DispatchRead(
        id=dispatch.id,
        order_id=dispatch.order_id,
        dispatch_number=dispatch.dispatch_number,
        status=dispatch.status,
        dispatched_at=dispatch.dispatched_at,
        delivered_at=dispatch.delivered_at,
        items=[
            DispatchItemRead(
                id=i.id,
                order_item_id=i.order_item_id,
                product_id=i.product_id,
                product_name=name,
                quantity=i.quantity,
                serialized_unit_id=i.serialized_unit_id,
            )
            for i, name in items
        ],
    )
