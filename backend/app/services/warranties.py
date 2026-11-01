"""Create warranties as part of the delivery transaction; never commit here."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.dates import add_months
from app.models.dispatch import Dispatch
from app.models.warranties import Warranty
from app.repositories import dispatch as dispatch_repo
from app.repositories import warranties as warranty_repo
from app.schemas.dispatch import WarrantyRead


def create_for_delivery(db: Session, dispatch: Dispatch, start_date: date) -> list[Warranty]:
    scanned = dispatch_repo.scanned_items(db, dispatch.id)
    warranties = []
    for item, product in dispatch_repo.lines(db, dispatch.order_id):
        if product.warranty_months == 0:
            continue
        units = [unit.id for row, unit in scanned if row.order_item_id == item.id]
        entries = (
            [(unit_id, Decimal("1")) for unit_id in units]
            if product.tracks_serial
            else [(None, item.quantity)]
        )
        for unit_id, quantity in entries:
            warranties.append(
                warranty_repo.create(
                    db,
                    order_id=dispatch.order_id,
                    order_item_id=item.id,
                    product_id=product.id,
                    serialized_unit_id=unit_id,
                    quantity=quantity,
                    start_date=start_date,
                    end_date=add_months(start_date, product.warranty_months),
                )
            )
    return warranties


def delivery_reads(
    db: Session, dispatch: Dispatch, warranties: list[Warranty]
) -> list[WarrantyRead]:
    products = {item.id: product for item, product in dispatch_repo.lines(db, dispatch.order_id)}
    serials = {
        unit.id: unit.serial_number for _, unit in dispatch_repo.scanned_items(db, dispatch.id)
    }
    return [
        WarrantyRead(
            id=row.id,
            order_id=row.order_id,
            order_item_id=row.order_item_id,
            product_id=row.product_id,
            product_name=products[row.order_item_id].name,
            serialized_unit_id=row.serialized_unit_id,
            serial=serials.get(row.serialized_unit_id),
            quantity=row.quantity,
            start_date=row.start_date,
            end_date=row.end_date,
        )
        for row in warranties
    ]
