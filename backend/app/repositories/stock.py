"""Stock receipt and on-hand queries; no commits or workflow decisions."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.enums import ProductCategory, SerialUnitStatus
from app.models.catalog import Product
from app.models.inventory import Inventory, SerializedUnit, StockReceipt, StockReceiptLine


def lock_products(db: Session, ids) -> dict[int, Product]:
    rows = db.scalars(
        select(Product)
        .where(Product.id.in_(ids))
        .order_by(Product.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {row.id: row for row in rows}


def existing_serials(db: Session, serials) -> list[str]:
    return list(
        db.scalars(
            select(SerializedUnit.serial_number)
            .where(SerializedUnit.serial_number.in_(serials))
            .order_by(SerializedUnit.serial_number)
        )
    )


def ensure_balances(db: Session, product_ids) -> None:
    """Create missing inventory rows (concurrency-safe); callers lock them afterwards."""
    if product_ids:
        db.execute(
            insert(Inventory)
            .values([{"product_id": pid} for pid in sorted(product_ids)])
            .on_conflict_do_nothing(index_elements=["product_id"])
        )


def add_unit(db: Session, **values) -> SerializedUnit:
    row = SerializedUnit(**values)
    db.add(row)
    db.flush()
    return row


def create_receipt(db: Session, **values) -> StockReceipt:
    row = StockReceipt(**values)
    db.add(row)
    db.flush()
    return row


def add_line(db: Session, **values) -> StockReceiptLine:
    row = StockReceiptLine(**values)
    db.add(row)
    db.flush()
    return row


def update(db: Session, row, **values) -> None:
    for key, value in values.items():
        setattr(row, key, value)
    db.flush()


def get_receipt(db: Session, receipt_id: int) -> StockReceipt | None:
    return db.get(StockReceipt, receipt_id)


def receipt_lines(db: Session, receipt_id: int):
    return db.execute(
        select(StockReceiptLine, Product)
        .join(Product, Product.id == StockReceiptLine.product_id)
        .where(StockReceiptLine.receipt_id == receipt_id)
        .order_by(StockReceiptLine.id)
    ).all()


def list_receipts(db: Session, *, date_from, date_to, limit, offset):
    stmt = select(StockReceipt)
    if date_from is not None:
        stmt = stmt.where(StockReceipt.received_on >= date_from)
    if date_to is not None:
        stmt = stmt.where(StockReceipt.received_on <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(StockReceipt.received_on.desc(), StockReceipt.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), total


def stock_page(db: Session, *, limit, offset):
    units = (
        select(SerializedUnit.product_id, func.count().label("units"))
        .where(SerializedUnit.status == SerialUnitStatus.IN_STOCK)
        .group_by(SerializedUnit.product_id)
        .subquery()
    )
    base = select(Product).where(
        Product.is_active.is_(True), Product.category != ProductCategory.SERVICE
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        select(
            Product,
            func.coalesce(Inventory.quantity_on_hand, 0).label("quantity"),
            func.coalesce(units.c.units, 0).label("units"),
        )
        .outerjoin(Inventory, Inventory.product_id == Product.id)
        .outerjoin(units, units.c.product_id == Product.id)
        .where(Product.is_active.is_(True), Product.category != ProductCategory.SERVICE)
        .order_by(Product.sku)
        .limit(limit)
        .offset(offset)
    ).all()
    return rows, total
