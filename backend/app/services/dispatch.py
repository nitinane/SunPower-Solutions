"""Locked warehouse actions: scan, send, and deliver with warranties."""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    DispatchStatus,
    OrderStatus,
    ProductCategory,
    SerialUnitStatus,
    StockMovementReason,
)
from app.core.validators import normalize_serial
from app.exceptions import BusinessRuleViolation, NotFound
from app.models.dispatch import Dispatch
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import customers as customer_repo
from app.repositories import dispatch as dispatch_repo
from app.repositories import inventory as inventory_repo
from app.repositories import orders as order_repo
from app.schemas.dispatch import DeliveryCreate, DispatchLine, DispatchRead, ScannedSerial
from app.schemas.quotes import QuoteCustomer, QuoteSite
from app.services import invoices as invoice_service
from app.services import warranties as warranty_service
from app.services.common import RequestMeta

BUSINESS_TZ = ZoneInfo("Asia/Kolkata")


class DispatchConflict(BusinessRuleViolation):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class SerialNotFound(NotFound):
    code = "SERIAL_NOT_FOUND"


def get_dispatch(db: Session, dispatch_id: int, *, lock: bool = False) -> Dispatch:
    dispatch = dispatch_repo.get_by_id(db, dispatch_id, lock=lock)
    if dispatch is None:
        raise NotFound("Dispatch not found")
    return dispatch


def to_read(db: Session, dispatch: Dispatch) -> DispatchRead:
    order = order_repo.get_by_id(db, dispatch.order_id)
    customer = customer_repo.get_by_id(db, order.customer_id)
    site = customer_repo.get_site(db, order.site_id)
    scanned = dispatch_repo.scanned_items(db, dispatch.id)
    lines = []
    for item, product in dispatch_repo.lines(db, order.id):
        serials = [
            ScannedSerial(
                dispatch_item_id=row.id,
                serialized_unit_id=unit.id,
                serial=unit.serial_number,
            )
            for row, unit in scanned
            if row.order_item_id == item.id
        ]
        lines.append(
            DispatchLine(
                order_item_id=item.id,
                sku=item.sku_snapshot,
                name=item.product_name_snapshot,
                qty=item.quantity,
                requires_serial=product.tracks_serial,
                scanned=len(serials),
                serials=serials,
            )
        )
    return DispatchRead(
        id=dispatch.id,
        dispatch_number=dispatch.dispatch_number,
        order_id=order.id,
        order_number=order.order_number,
        status=dispatch.status,
        customer=QuoteCustomer(
            id=customer.id, name=customer.full_name, phone=customer.phone_e164, email=customer.email
        ),
        site=QuoteSite.model_validate(site, from_attributes=True),
        lines=lines,
        dispatched_at=dispatch.dispatched_at,
        delivered_at=dispatch.delivered_at,
        receiver_name=dispatch.receiver_name,
        created_at=dispatch.created_at,
    )


def list_dispatches(db: Session, *, status: DispatchStatus | None, page: int, page_size: int):
    rows, total = dispatch_repo.list_page(
        db, status=status, limit=page_size, offset=(page - 1) * page_size
    )
    return [to_read(db, row) for row in rows], total


def _require_pick(dispatch: Dispatch) -> None:
    if dispatch.status != DispatchStatus.DRAFT:
        raise DispatchConflict("DISPATCH_LOCKED", "Only a draft pick list can be changed or sent")


def _require_stock(unit) -> None:
    if unit.status in (SerialUnitStatus.DISPATCHED, SerialUnitStatus.INSTALLED):
        raise DispatchConflict("SERIAL_ALREADY_SHIPPED", f"{unit.serial_number} already shipped")
    if unit.status != SerialUnitStatus.IN_STOCK:
        raise DispatchConflict("SERIAL_NOT_IN_STOCK", f"{unit.serial_number} is not in stock")


def scan(db: Session, dispatch_id: int, serial: str, *, actor: User, meta=None) -> Dispatch:
    dispatch = get_dispatch(db, dispatch_id, lock=True)
    _require_pick(dispatch)
    unit = inventory_repo.serial_by_number(db, normalize_serial(serial))
    if unit is None:
        raise SerialNotFound("Serial number not found")
    scanned = dispatch_repo.scanned_items(db, dispatch.id)
    if any(row.serialized_unit_id == unit.id for row, _ in scanned):
        return dispatch
    lines = dispatch_repo.lines(db, dispatch.order_id)
    matches = [
        (item, product)
        for item, product in lines
        if item.product_id == unit.product_id and product.tracks_serial
    ]
    if not matches:
        # Product lookup stays in the repository layer.
        product = dispatch_repo.product_for_serial(db, unit.product_id)
        needed = ", ".join(item.sku_snapshot for item, p in lines if p.tracks_serial)
        raise DispatchConflict(
            "SERIAL_WRONG_PRODUCT", f"This is a {product.sku}; this order needs {needed}"
        )
    item = next(
        (
            item
            for item, _ in matches
            if sum(1 for row, _ in scanned if row.order_item_id == item.id) < item.quantity
        ),
        None,
    )
    if item is None:
        raise DispatchConflict(
            "LINE_ALREADY_COMPLETE", "That product line is already fully scanned"
        )
    _require_stock(unit)
    try:
        row = dispatch_repo.add_item(
            db,
            dispatch_id=dispatch.id,
            order_item_id=item.id,
            product_id=unit.product_id,
            serialized_unit_id=unit.id,
            quantity=Decimal("1"),
        )
    except IntegrityError as exc:
        db.rollback()
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) != (
            "uq_dispatch_serialized_unit"
        ):
            raise
        raise DispatchConflict(
            "SERIAL_ALREADY_SHIPPED", "Serial already assigned to a dispatch"
        ) from None
    _audit(
        db,
        actor,
        "dispatch.scanned",
        "dispatch",
        dispatch.id,
        None,
        {"dispatch_item_id": row.id, "serial": unit.serial_number},
        meta,
    )
    db.commit()
    db.refresh(dispatch)
    return dispatch


def unscan(db: Session, dispatch_id: int, item_id: int, *, actor: User, meta=None) -> Dispatch:
    dispatch = get_dispatch(db, dispatch_id, lock=True)
    _require_pick(dispatch)
    row = next(
        (row for row, _ in dispatch_repo.scanned_items(db, dispatch.id) if row.id == item_id), None
    )
    if row is None:
        raise NotFound("Scanned item not found on this dispatch")
    old = {"dispatch_item_id": row.id, "serialized_unit_id": row.serialized_unit_id}
    dispatch_repo.delete_item(db, row)
    _audit(db, actor, "dispatch.scan_removed", "dispatch", dispatch.id, old, None, meta)
    db.commit()
    db.refresh(dispatch)
    return dispatch


def send(db: Session, dispatch_id: int, *, actor: User, meta=None) -> Dispatch:
    dispatch = get_dispatch(db, dispatch_id, lock=True)
    _require_pick(dispatch)
    lines = dispatch_repo.lines(db, dispatch.order_id)
    scanned = dispatch_repo.scanned_items(db, dispatch.id)
    missing = []
    quantities = defaultdict(lambda: Decimal("0"))
    products = {}
    for item, product in lines:
        if product.category == ProductCategory.SERVICE:
            continue
        quantities[product.id] += item.quantity
        products[product.id] = product
        count = sum(1 for row, _ in scanned if row.order_item_id == item.id)
        if product.tracks_serial and count != item.quantity:
            missing.append(f"{item.product_name_snapshot} {count}/{item.quantity:g}")
    if missing:
        raise DispatchConflict("SCAN_INCOMPLETE", "Missing scans: " + ", ".join(missing))
    units = inventory_repo.lock_serials(db, [unit.id for _, unit in scanned])
    for unit in units:
        _require_stock(unit)
    balances = inventory_repo.lock_balances(
        db, [pid for pid, p in products.items() if not p.tracks_serial]
    )
    for pid, quantity in quantities.items():
        if products[pid].tracks_serial:
            continue
        balance = balances.get(pid)
        if balance is None or balance.quantity_on_hand - balance.quantity_reserved < quantity:
            raise DispatchConflict(
                "INSUFFICIENT_STOCK", f"Insufficient stock for {products[pid].name}"
            )
    # Every validation passes before changing any stock.
    order = order_repo.get_by_id_for_update(db, dispatch.order_id)
    for pid, balance in balances.items():
        inventory_repo.update(
            db, balance, quantity_on_hand=balance.quantity_on_hand - quantities[pid]
        )
    for unit in units:
        inventory_repo.update(db, unit, status=SerialUnitStatus.DISPATCHED)
    for pid, quantity in quantities.items():
        inventory_repo.add_movement(
            db,
            product_id=pid,
            order_id=order.id,
            quantity_delta=-quantity,
            reason=StockMovementReason.DISPATCH,
            performed_by=actor.id,
            reference_type="dispatch",
            reference_id=dispatch.id,
        )
    old_status = dispatch.status
    dispatch_repo.update(
        db,
        dispatch,
        status=DispatchStatus.DISPATCHED,
        dispatched_at=datetime.now(UTC),
        dispatched_by=actor.id,
    )
    old_order = order.status
    order_repo.update(db, order, {"status": OrderStatus.DISPATCHED})
    _audit(
        db,
        actor,
        "order.dispatched",
        "order",
        order.id,
        {"status": old_order},
        {"status": order.status},
        meta,
    )
    _audit(
        db,
        actor,
        "dispatch.sent",
        "dispatch",
        dispatch.id,
        {"status": old_status},
        {"status": dispatch.status},
        meta,
    )
    db.commit()
    db.refresh(dispatch)
    return dispatch


def deliver(db: Session, dispatch_id: int, data: DeliveryCreate, *, actor: User, meta=None):
    dispatch = get_dispatch(db, dispatch_id, lock=True)
    if dispatch.status == DispatchStatus.DELIVERED:
        raise DispatchConflict("ALREADY_DELIVERED", "Dispatch has already been delivered")
    if dispatch.status != DispatchStatus.DISPATCHED:
        raise DispatchConflict("DISPATCH_LOCKED", "Only a dispatched order can be delivered")
    delivered_at = (data.delivered_at or datetime.now(UTC)).astimezone(UTC)
    order = order_repo.get_by_id_for_update(db, dispatch.order_id)
    old_status = dispatch.status
    dispatch_repo.update(
        db,
        dispatch,
        status=DispatchStatus.DELIVERED,
        receiver_name=data.receiver_name,
        delivered_at=delivered_at,
        delivered_by=actor.id,
    )
    warranties = warranty_service.create_for_delivery(
        db, dispatch, delivered_at.astimezone(BUSINESS_TZ).date()
    )
    old_order = order.status
    order_repo.update(db, order, {"status": OrderStatus.DELIVERED})
    invoice_service.create_for_order(db, order, actor=actor, meta=meta)
    _audit(
        db,
        actor,
        "order.delivered",
        "order",
        order.id,
        {"status": old_order},
        {"status": order.status},
        meta,
    )
    _audit(
        db,
        actor,
        "dispatch.delivered",
        "dispatch",
        dispatch.id,
        {"status": old_status},
        {
            "status": dispatch.status,
            "receiver_name": data.receiver_name,
            "delivered_at": delivered_at.isoformat(),
        },
        meta,
    )
    _audit(
        db,
        actor,
        "warranty.created",
        "dispatch",
        dispatch.id,
        None,
        {"count": len(warranties)},
        meta,
    )
    db.commit()
    db.refresh(dispatch)
    return dispatch, warranties


def _audit(db, actor, action, entity_type, entity_id, old, new, meta):
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old,
        new_data=new,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )
