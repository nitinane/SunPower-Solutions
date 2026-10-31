"""Stock receiving from suppliers and the on-hand view."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import ProductCategory, SerialUnitStatus, StockMovementReason
from app.exceptions import BusinessRuleViolation, NotFound, ValidationFailed
from app.repositories import auth as audit_repo
from app.repositories import inventory as inventory_repo
from app.repositories import stock as repo
from app.schemas.stock import ReceiptCreate, ReceiptLineRead, ReceiptRead, StockRow
from app.services.catalog import money
from app.services.common import RequestMeta

BUSINESS_TZ = ZoneInfo("Asia/Kolkata")
LOW_STOCK_SERIAL = Decimal("5")
LOW_STOCK_BULK = Decimal("50")


class SerialCountMismatch(ValidationFailed):
    code = "SERIAL_COUNT_MISMATCH"


class SerialExists(BusinessRuleViolation):
    code = "SERIAL_EXISTS"


def _today():
    return datetime.now(UTC).astimezone(BUSINESS_TZ).date()


def _validate(data: ReceiptCreate, products) -> list[str]:
    if data.received_on > _today():
        raise ValidationFailed(
            "Received date cannot be in the future", fields={"received_on": "Not in the future"}
        )
    serials: list[str] = []
    for index, line in enumerate(data.lines):
        product = products.get(line.product_id)
        if product is None or not product.is_active or product.category == ProductCategory.SERVICE:
            raise ValidationFailed(
                "Choose an active stock product",
                fields={f"lines.{index}.product_id": "Invalid product"},
            )
        if not product.tracks_serial:
            if line.serials:
                raise ValidationFailed(
                    f"{product.sku} has no serial numbers",
                    fields={f"lines.{index}.serials": "Leave empty for this product"},
                )
            continue
        given = line.serials or []
        if Decimal(len(given)) != line.qty:
            raise SerialCountMismatch(
                f"{product.sku}: {len(given)} serials for qty {line.qty:g}",
                fields={f"lines.{index}.serials": "One serial per unit"},
            )
        serials.extend(given)
    duplicates = sorted({s for s in serials if serials.count(s) > 1})
    if duplicates:
        raise ValidationFailed(
            "Duplicate serials in this receipt: " + ", ".join(duplicates),
            fields={"lines": "Each serial may appear once"},
        )
    return serials


def create_receipt(db: Session, data: ReceiptCreate, *, actor, meta=None):
    products = repo.lock_products(db, {line.product_id for line in data.lines})
    serials = _validate(data, products)
    taken = repo.existing_serials(db, serials) if serials else []
    if taken:
        raise SerialExists("Serials already exist: " + ", ".join(taken))
    bulk_ids = {
        line.product_id for line in data.lines if not products[line.product_id].tracks_serial
    }
    repo.ensure_balances(db, bulk_ids)
    balances = inventory_repo.lock_balances(db, sorted(bulk_ids))
    receipt = repo.create_receipt(
        db,
        receipt_number=f"RCV-TMP-{uuid4().hex[:20]}",
        supplier_name=data.supplier_name,
        supplier_invoice_ref=data.supplier_invoice_ref,
        received_on=data.received_on,
        created_by=actor.id,
    )
    repo.update(db, receipt, receipt_number=f"RCV-{receipt.id:06d}")
    now = datetime.now(UTC)
    snapshot = []
    for line in data.lines:
        product = products[line.product_id]
        repo.add_line(
            db,
            receipt_id=receipt.id,
            product_id=product.id,
            qty=line.qty,
            unit_cost=line.unit_cost,
        )
        if product.tracks_serial:
            try:
                for serial in line.serials:
                    repo.add_unit(
                        db,
                        product_id=product.id,
                        serial_number=serial,
                        status=SerialUnitStatus.IN_STOCK,
                        received_at=now,
                    )
            except IntegrityError:
                db.rollback()
                raise SerialExists("A serial in this receipt was just added") from None
        else:
            balance = balances[product.id]
            inventory_repo.update(
                db, balance, quantity_on_hand=balance.quantity_on_hand + line.qty
            )
        inventory_repo.add_movement(
            db,
            product_id=product.id,
            quantity_delta=line.qty,
            reason=StockMovementReason.PURCHASE,
            performed_by=actor.id,
            reference_type="stock_receipt",
            reference_id=receipt.id,
        )
        repo.update(db, product, cost_price=line.unit_cost)
        snapshot.append(
            {
                "product_id": product.id,
                "qty": str(line.qty),
                "unit_cost": str(line.unit_cost),
                "serials": line.serials or [],
            }
        )
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id,
        action="stock.received",
        entity_type="stock_receipt",
        entity_id=receipt.id,
        old_data=None,
        new_data={
            "receipt_number": receipt.receipt_number,
            "supplier_name": receipt.supplier_name,
            "supplier_invoice_ref": receipt.supplier_invoice_ref,
            "lines": snapshot,
        },
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )
    db.commit()
    db.refresh(receipt)
    return receipt


def to_read(db: Session, receipt) -> ReceiptRead:
    lines = [
        ReceiptLineRead(
            id=line.id,
            product_id=product.id,
            sku=product.sku,
            name=product.name,
            qty=line.qty,
            unit_cost=line.unit_cost,
            line_total=money(line.qty * line.unit_cost),
        )
        for line, product in repo.receipt_lines(db, receipt.id)
    ]
    return ReceiptRead(
        id=receipt.id,
        receipt_number=receipt.receipt_number,
        supplier_name=receipt.supplier_name,
        supplier_invoice_ref=receipt.supplier_invoice_ref,
        received_on=receipt.received_on,
        created_by=receipt.created_by,
        created_at=receipt.created_at,
        total=money(sum((line.line_total for line in lines), Decimal("0"))),
        lines=lines,
    )


def get_receipt(db: Session, receipt_id: int):
    receipt = repo.get_receipt(db, receipt_id)
    if receipt is None:
        raise NotFound("Stock receipt not found")
    return receipt


def list_receipts(db: Session, *, date_from, date_to, page, page_size):
    rows, total = repo.list_receipts(
        db, date_from=date_from, date_to=date_to, limit=page_size, offset=(page - 1) * page_size
    )
    return [to_read(db, row) for row in rows], total


def stock(db: Session, *, page, page_size):
    rows, total = repo.stock_page(db, limit=page_size, offset=(page - 1) * page_size)
    items = []
    for product, quantity, units in rows:
        on_hand = Decimal(units) if product.tracks_serial else Decimal(quantity)
        limit = LOW_STOCK_SERIAL if product.tracks_serial else LOW_STOCK_BULK
        items.append(
            StockRow(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                category=product.category,
                requires_serial=product.tracks_serial,
                on_hand=on_hand,
                low_stock=on_hand < limit,
            )
        )
    return items, total
