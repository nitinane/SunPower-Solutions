"""Ticket and support lookup queries; no commits or workflow decisions."""

from sqlalchemy import func, select, union
from sqlalchemy.orm import Session

from app.core.enums import SerialUnitStatus, TicketStatus
from app.models.auth import AuditLog
from app.models.catalog import Product
from app.models.customers import Customer, Site
from app.models.dispatch import Dispatch, DispatchItem
from app.models.inventory import SerializedUnit
from app.models.orders import Order, OrderItem
from app.models.service_tickets import SupportTicket, TicketCharge
from app.models.warranties import Warranty


def lock_customer(db: Session, customer_id: int):
    return db.scalars(
        select(Customer)
        .where(Customer.id == customer_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def get(db: Session, ticket_id: int, *, lock: bool = False):
    stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalars(stmt).first()


def create(db: Session, **values):
    row = SupportTicket(**values)
    db.add(row)
    db.flush()
    return row


def update(db: Session, row: SupportTicket, **values):
    for key, value in values.items():
        setattr(row, key, value)
    db.flush()


def add_charge(db: Session, **values):
    row = TicketCharge(**values)
    db.add(row)
    db.flush()
    return row


def charges(db: Session, ticket_id: int):
    return list(
        db.scalars(
            select(TicketCharge)
            .where(TicketCharge.ticket_id == ticket_id)
            .order_by(TicketCharge.id)
        )
    )


def history(db: Session, ticket_id: int):
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "ticket", AuditLog.entity_id == ticket_id)
            .order_by(AuditLog.created_at, AuditLog.id)
        )
    )


def list_page(db: Session, *, status, assigned_to, limit, offset):
    stmt = select(SupportTicket)
    if status is not None:
        stmt = stmt.where(SupportTicket.status == status)
    if assigned_to is not None:
        stmt = stmt.where(SupportTicket.assigned_to == assigned_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    return list(
        db.scalars(
            stmt.order_by(SupportTicket.opened_at.desc(), SupportTicket.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ), total


def target(db: Session, *, serial_id: int | None, order_item_id: int | None):
    stmt = select(OrderItem, Order, Product).join(Order, Order.id == OrderItem.order_id)
    stmt = stmt.join(Product, Product.id == OrderItem.product_id)
    if serial_id is not None:
        # Shipped units come via the dispatch; warranty replacements via their warranty.
        stmt = stmt.where(
            OrderItem.id.in_(
                union(
                    select(DispatchItem.order_item_id).where(
                        DispatchItem.serialized_unit_id == serial_id
                    ),
                    select(Warranty.order_item_id).where(Warranty.serialized_unit_id == serial_id),
                )
            )
        )
    else:
        stmt = stmt.where(OrderItem.id == order_item_id)
    return db.execute(stmt).first()


def warranty(db: Session, *, serial_id, order_item_id):
    stmt = select(Warranty)
    if serial_id is not None:
        stmt = stmt.where(Warranty.serialized_unit_id == serial_id)
    else:
        stmt = stmt.where(
            Warranty.order_item_id == order_item_id, Warranty.serialized_unit_id.is_(None)
        )
    return db.scalars(stmt).first()


def warranty_for_update(db: Session, serial_id):
    return db.scalars(
        select(Warranty)
        .where(Warranty.serialized_unit_id == serial_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def _customer_serial_units():
    """(customer_id, unit_id) for shipped units and warranty replacement units."""
    shipped = (
        select(Order.customer_id, DispatchItem.serialized_unit_id.label("unit_id"))
        .join(Dispatch, Dispatch.order_id == Order.id)
        .join(DispatchItem, DispatchItem.dispatch_id == Dispatch.id)
        .where(DispatchItem.serialized_unit_id.is_not(None))
    )
    replaced = select(Order.customer_id, Warranty.serialized_unit_id.label("unit_id")).join(
        Warranty, Warranty.order_id == Order.id
    ).where(Warranty.serialized_unit_id.is_not(None))
    return union(shipped, replaced).subquery()


def products(db: Session, ids):
    return {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(ids)))}


def customers_by_phone(db: Session, phone):
    return list(
        db.scalars(
            select(Customer)
            .where(Customer.phone_e164 == phone)
            .order_by(Customer.id.desc())
            .limit(10)
        )
    )


def customers_by_serial(db: Session, serial):
    links = _customer_serial_units()
    stmt = (
        select(Customer)
        .join(links, links.c.customer_id == Customer.id)
        .join(SerializedUnit, SerializedUnit.id == links.c.unit_id)
        .where(SerializedUnit.serial_number == serial)
        .distinct()
        .order_by(Customer.id)
        .limit(10)
    )
    return list(db.scalars(stmt))


def customers_by_name(db: Session, name):
    escaped = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return list(
        db.scalars(
            select(Customer)
            .where(Customer.full_name.ilike(escaped + "%", escape="\\"))
            .order_by(Customer.full_name, Customer.id)
            .limit(10)
        )
    )


def customer_sites(db: Session, customer_id):
    return list(db.scalars(select(Site).where(Site.customer_id == customer_id).order_by(Site.id)))


def customer_orders(db: Session, customer_id):
    return list(
        db.scalars(
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
    )


def customer_units(db: Session, customer_id):
    """Units the customer has now (faulty units returned in a swap are left out)."""
    links = _customer_serial_units()
    return db.execute(
        select(SerializedUnit, Product, Warranty)
        .join(Product, Product.id == SerializedUnit.product_id)
        .outerjoin(Warranty, Warranty.serialized_unit_id == SerializedUnit.id)
        .where(
            SerializedUnit.id.in_(
                select(links.c.unit_id).where(links.c.customer_id == customer_id)
            ),
            SerializedUnit.status != SerialUnitStatus.RETURNED,
        )
        .order_by(SerializedUnit.id)
    ).all()


def customer_open_tickets(db: Session, customer_id):
    return list(
        db.scalars(
            select(SupportTicket)
            .where(
                SupportTicket.customer_id == customer_id,
                SupportTicket.status.not_in([TicketStatus.CLOSED, TicketStatus.CANCELLED]),
            )
            .order_by(SupportTicket.opened_at.desc())
        )
    )
