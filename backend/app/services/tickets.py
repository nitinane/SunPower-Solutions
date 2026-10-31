"""Warranty decisions, repair billing, and customer-only closure."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import ChargeType, ProductCategory, StockMovementReason, TicketStatus, UserRole
from app.core.validators import normalize_phone, normalize_serial
from app.exceptions import BusinessRuleViolation, Forbidden, NotFound, ValidationFailed
from app.repositories import auth as audit_repo
from app.repositories import inventory as inventory_repo
from app.repositories import tickets as repo
from app.repositories import users as user_repo
from app.schemas.auth import AuditEntryRead
from app.schemas.quotes import QuoteCustomer, QuoteSite
from app.schemas.tickets import (
    SupportOrder,
    SupportResult,
    SupportTicketRef,
    SupportUnit,
    TicketChargeRead,
    TicketCreate,
    TicketRead,
)
from app.services.catalog import money
from app.services.common import RequestMeta

BUSINESS_TZ = ZoneInfo("Asia/Kolkata")
ZERO = Decimal("0.00")


class TicketConflict(BusinessRuleViolation):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def _now():
    return datetime.now(UTC)


def _today():
    return _now().astimezone(BUSINESS_TZ).date()


def get_ticket(db, ticket_id, *, actor, lock=False):
    ticket = repo.get(db, ticket_id, lock=lock)
    if ticket is None:
        raise NotFound("Ticket not found")
    if actor.role == UserRole.TECHNICIAN and ticket.assigned_to != actor.id:
        raise Forbidden("You can only access your assigned tickets")
    return ticket


def to_read(db, ticket):
    values = {
        name: getattr(ticket, name)
        for name in TicketRead.model_fields
        if name not in {"coverage_label", "charges", "history"}
    }
    return TicketRead(
        **values,
        coverage_label="Under warranty – free"
        if ticket.under_warranty
        else "Out of warranty – billable",
        charges=[
            TicketChargeRead(
                **{
                    name: getattr(row, name)
                    for name in TicketChargeRead.model_fields
                    if name != "amount"
                },
                amount=money(row.quantity * row.customer_price),
            )
            for row in repo.charges(db, ticket.id)
        ],
        history=[
            AuditEntryRead.model_validate(row, from_attributes=True)
            for row in repo.history(db, ticket.id)
        ],
    )


def list_tickets(db, *, actor, status, assigned_to_me, page, page_size):
    assigned_to = actor.id if assigned_to_me or actor.role == UserRole.TECHNICIAN else None
    rows, total = repo.list_page(
        db, status=status, assigned_to=assigned_to, limit=page_size, offset=(page - 1) * page_size
    )
    return [to_read(db, row) for row in rows], total


def create_ticket(db: Session, data: TicketCreate, *, actor, meta=None):
    customer = repo.lock_customer(db, data.customer_id)
    if customer is None:
        raise NotFound("Customer not found")
    target = repo.target(db, serial_id=data.serialized_unit_id, order_item_id=data.order_item_id)
    if target is None or target[1].customer_id != customer.id:
        raise ValidationFailed(
            "The selected item does not belong to this customer",
            fields={"customer_id": "Choose the customer who owns this item"},
        )
    item, order, product = target
    if data.order_item_id is not None and product.tracks_serial:
        raise ValidationFailed(
            "Choose the serial unit for a serialized product",
            fields={"serialized_unit_id": "Required for this product"},
        )
    warranty = repo.warranty(db, serial_id=data.serialized_unit_id, order_item_id=item.id)
    covered = bool(warranty and warranty.voided_at is None and warranty.end_date >= _today())
    ticket = repo.create(
        db,
        ticket_number=f"TKT-TMP-{uuid4().hex[:20]}",
        customer_id=customer.id,
        site_id=order.site_id,
        faulty_serial_unit_id=data.serialized_unit_id,
        order_item_id=data.order_item_id,
        warranty_id=warranty.id if warranty else None,
        status=TicketStatus.OPEN,
        under_warranty=covered,
        fault_code=data.fault_code,
        issue_description=data.issue_description,
        priority=data.priority,
    )
    repo.update(db, ticket, ticket_number=f"TKT-{ticket.id:06d}")
    _audit(
        db,
        actor,
        "ticket.created",
        ticket,
        None,
        {"status": ticket.status, "under_warranty": covered},
        meta,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def _require(ticket, status):
    if ticket.status != status:
        raise TicketConflict(
            "TICKET_STATUS_INVALID", f"Ticket must be {status}; it is {ticket.status}"
        )


def assign(db, ticket_id, data, *, actor, meta=None):
    ticket = get_ticket(db, ticket_id, actor=actor, lock=True)
    _require(ticket, TicketStatus.OPEN)
    technician = user_repo.get_by_id(db, data.technician_id)
    if technician is None or not technician.is_active or technician.role != UserRole.TECHNICIAN:
        raise ValidationFailed(
            "Choose an active technician", fields={"technician_id": "Invalid technician"}
        )
    old = {"status": ticket.status, "assigned_to": ticket.assigned_to}
    repo.update(
        db,
        ticket,
        status=TicketStatus.ASSIGNED,
        assigned_to=technician.id,
        visit_date=data.visit_date,
    )
    _audit(
        db,
        actor,
        "ticket.assigned",
        ticket,
        old,
        {
            "status": ticket.status,
            "assigned_to": technician.id,
            "visit_date": data.visit_date.isoformat(),
        },
        meta,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def resolve(db, ticket_id, data, *, actor, meta=None):
    ticket = get_ticket(db, ticket_id, actor=actor, lock=True)
    _require(ticket, TicketStatus.ASSIGNED)
    total_hours = money((ticket.labour_hours or ZERO) + data.labour_hours)
    if total_hours > Decimal("999.99"):
        raise ValidationFailed(
            "Ticket labour hours exceed the supported total",
            fields={"labour_hours": "Total across visits must not exceed 999.99"},
        )
    products = repo.products(db, [part.product_id for part in data.parts])
    for part in data.parts:
        product = products.get(part.product_id)
        if product is None or product.tracks_serial or product.category == ProductCategory.SERVICE:
            raise ValidationFailed(
                "Parts must be non-serialized stock products",
                fields={"parts": "Serialized replacements are not supported"},
            )
    balances = inventory_repo.lock_balances(db, list(products))
    for part in data.parts:
        balance = balances.get(part.product_id)
        if balance is None or balance.quantity_on_hand - balance.quantity_reserved < part.qty:
            raise TicketConflict(
                "INSUFFICIENT_STOCK", f"Insufficient stock for {products[part.product_id].name}"
            )
    part_subtotal, labour_amount, gst = ZERO, ZERO, ZERO
    charge_snapshots = []
    for part in data.parts:
        product = products[part.product_id]
        balance = balances[part.product_id]
        inventory_repo.update(db, balance, quantity_on_hand=balance.quantity_on_hand - part.qty)
        inventory_repo.add_movement(
            db,
            product_id=product.id,
            quantity_delta=-part.qty,
            reason=StockMovementReason.SERVICE,
            performed_by=actor.id,
            reference_type="ticket",
            reference_id=ticket.id,
        )
        price = ZERO if ticket.under_warranty else money(product.sale_price)
        amount = money(part.qty * price)
        line_gst = money(amount * product.gst_rate / Decimal("100"))
        repo.add_charge(
            db,
            ticket_id=ticket.id,
            charge_type=ChargeType.PART,
            product_id=product.id,
            description=product.name,
            quantity=part.qty,
            cost_amount=money(part.qty * product.cost_price),
            customer_price=price,
            covered_by_warranty=ticket.under_warranty,
        )
        part_subtotal += amount
        gst += line_gst
        charge_snapshots.append(
            {
                "product_id": product.id,
                "qty": str(part.qty),
                "unit_price": str(price),
                "gst_percent": str(product.gst_rate),
                "amount": str(amount),
                "gst": str(line_gst),
            }
        )
    if data.labour_hours > 0:
        rate = ZERO if ticket.under_warranty else money(settings.service_labour_rate_per_hour)
        labour_amount = money(data.labour_hours * rate)
        gst += money(labour_amount * settings.service_labour_gst_percent / Decimal("100"))
        repo.add_charge(
            db,
            ticket_id=ticket.id,
            charge_type=ChargeType.LABOUR,
            quantity=data.labour_hours,
            description="Repair labour",
            customer_price=rate,
            cost_amount=ZERO,
            covered_by_warranty=ticket.under_warranty,
        )
    old = {"status": ticket.status}
    repo.update(
        db,
        ticket,
        status=TicketStatus.RESOLVED,
        resolved_at=_now(),
        work_notes=data.work_notes,
        labour_hours=total_hours,
        parts_subtotal=money(ticket.parts_subtotal + part_subtotal),
        labour_amount=money(ticket.labour_amount + labour_amount),
        gst=money(ticket.gst + gst),
        total=money(ticket.total + part_subtotal + labour_amount + gst),
    )
    _audit(
        db,
        actor,
        "ticket.resolved",
        ticket,
        old,
        {
            "status": ticket.status,
            "parts": charge_snapshots,
            "total": str(ticket.total),
            "labour_rate": str(settings.service_labour_rate_per_hour),
            "labour_gst_percent": str(settings.service_labour_gst_percent),
            "work_notes": data.work_notes,
            "labour_hours": str(data.labour_hours),
        },
        meta,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def confirm(db, ticket_id, data, *, actor, meta=None):
    ticket = get_ticket(db, ticket_id, actor=actor, lock=True)
    _require(ticket, TicketStatus.RESOLVED)
    old = {"status": ticket.status}
    changes = {"status": TicketStatus.CLOSED if data.confirmed else TicketStatus.OPEN}
    if data.confirmed:
        changes.update(confirmed_by_name=data.customer_name, customer_confirmed_at=_now())
    repo.update(db, ticket, **changes)
    _audit(
        db,
        actor,
        "ticket.confirmed" if data.confirmed else "ticket.reopened",
        ticket,
        old,
        {"status": ticket.status, "customer_name": data.customer_name, "note": data.note},
        meta,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def search(db, query: str):
    query = query.strip()
    if not query:
        return []
    try:
        phone = normalize_phone(query) if re.fullmatch(r"[\d\s+().-]+", query) else None
    except ValueError:
        phone = None
    if phone:
        customers = repo.customers_by_phone(db, phone)
    else:
        try:
            customers = repo.customers_by_serial(db, normalize_serial(query))
        except ValueError:
            customers = []
        if not customers:
            customers = repo.customers_by_name(db, query)
    today = _today()
    results = []
    for customer in customers:
        units = []
        for unit, product, warranty in repo.customer_units(db, customer.id):
            active = bool(warranty and warranty.voided_at is None and warranty.end_date >= today)
            units.append(
                SupportUnit(
                    serialized_unit_id=unit.id,
                    serial=unit.serial_number,
                    product=product.name,
                    warranty_end=warranty.end_date if warranty else None,
                    warranty_status="active" if active else "expired",
                    days_left=max((warranty.end_date - today).days, 0) if active else 0,
                )
            )
        results.append(
            SupportResult(
                customer=QuoteCustomer(
                    id=customer.id,
                    name=customer.full_name,
                    phone=customer.phone_e164,
                    email=customer.email,
                ),
                sites=[
                    QuoteSite.model_validate(row, from_attributes=True)
                    for row in repo.customer_sites(db, customer.id)
                ],
                orders=[
                    SupportOrder(id=row.id, number=row.order_number, status=row.status)
                    for row in repo.customer_orders(db, customer.id)
                ],
                units=units,
                open_tickets=[
                    SupportTicketRef.model_validate(row, from_attributes=True)
                    for row in repo.customer_open_tickets(db, customer.id)
                ],
            )
        )
    return results


def _audit(db, actor, action, ticket, old, new, meta):
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id,
        action=action,
        entity_type="ticket",
        entity_id=ticket.id,
        old_data=old,
        new_data=new,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )
