"""Create warranties as part of the delivery transaction; never commit here."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.dates import add_months
from app.models.dispatch import Dispatch
from app.models.warranties import Warranty
from app.repositories import dispatch as dispatch_repo
from app.repositories import warranties as warranty_repo


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
