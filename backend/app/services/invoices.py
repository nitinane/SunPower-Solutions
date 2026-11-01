"""
GST invoices with gapless sequential numbers.

- Order invoice: created inside dispatch delivery (the moment of supply), same transaction.
- Service invoice: created inside ticket confirmation when a paid (non-warranty) repair closes.
- Number: INV/<FY>/<000001>. The Indian financial year runs April-March (IST dates). The
  per-year counter row is locked FOR UPDATE inside the caller's transaction, so a rollback
  undoes both the invoice and the number: no gaps, no duplicates.
- Lines are snapshots; totals are sums of the quantized lines and must equal the order's.
- GST split: site state == company state -> CGST + SGST (half each, SGST takes the odd paisa),
  otherwise IGST.
- Invoices never change after creation (no update/delete; corrections = credit notes, later).
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dates import today_ist
from app.core.enums import ChargeType, InvoiceKind, InvoiceStatus, OrderStatus
from app.exceptions import BusinessRuleViolation, NotFound
from app.models.invoices import Invoice
from app.models.orders import Order
from app.models.service_tickets import SupportTicket
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import customers as customer_repo
from app.repositories import invoices as invoice_repo
from app.repositories import orders as order_repo
from app.repositories import payments as payment_repo
from app.repositories import quotes as quote_repo
from app.repositories import tickets as ticket_repo
from app.schemas.invoices import (
    InvoiceBuyer,
    InvoiceLineRead,
    InvoiceRead,
    InvoiceSeller,
    InvoiceSummary,
)
from app.schemas.quotes import QuoteSite
from app.services.catalog import money, price_line
from app.services.common import RequestMeta

MAX_PAGE_SIZE = 100
INVOICEABLE_ORDER_STATUSES = frozenset(
    {OrderStatus.DELIVERED, OrderStatus.INSTALLED, OrderStatus.COMPLETED}
)
HUNDRED = Decimal("100")


class OrderNotDelivered(BusinessRuleViolation):
    code = "ORDER_NOT_DELIVERED"


# ---------------------------------------------------------------- Pure helpers (tested)

def financial_year(day: date) -> str:
    """April-March: 2026-11-01 -> '2026-27', 2027-03-31 -> '2026-27', 2027-04-01 -> '2027-28'."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def split_gst(gst: Decimal, place_of_supply: str) -> tuple[Decimal, Decimal, Decimal]:
    """(cgst, sgst, igst). Intra-state halves the tax; cgst + sgst == gst exactly."""
    gst = money(gst)
    if place_of_supply.strip().casefold() == settings.company_state.strip().casefold():
        cgst = money(gst / 2)
        return cgst, gst - cgst, Decimal("0.00")
    return Decimal("0.00"), Decimal("0.00"), gst


def format_number(fy: str, number: int) -> str:
    return f"INV/{fy}/{number:06d}"


# ---------------------------------------------------------------- Create (inside caller's tx)

def create_for_order(
    db: Session,
    order: Order,
    *,
    actor: User,
    meta: RequestMeta | None = None,
    invoice_date: date | None = None,
) -> tuple[Invoice, bool]:
    """Invoice for a delivered order. Returns (invoice, created). Does not commit."""
    existing = invoice_repo.get_by_order(db, order.id)
    if existing is not None:
        return existing, False

    lines = []
    for item in order_repo.list_items(db, order.id):
        priced = price_line(
            product_id=item.product_id,
            sku=item.sku_snapshot,
            name=item.product_name_snapshot,
            qty=item.quantity,
            unit_price=item.unit_price,
            gst_percent=item.gst_rate,
        )
        lines.append(
            {
                "description_snapshot": item.product_name_snapshot,
                "sku": item.sku_snapshot,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "gst_rate": item.gst_rate,
                "taxable": priced.line_total,
                "gst_amount": priced.gst_amount,
            }
        )
    quote = quote_repo.get_by_id(db, order.quote_id)
    taxable, gst = _sums(lines)
    if (taxable, gst, taxable + gst) != (
        money(quote.subtotal), money(quote.tax_total), money(quote.total)
    ):
        # Same snapshots, same rounding: a mismatch is a bug, never print a wrong invoice.
        raise RuntimeError(f"Invoice totals differ from order {order.order_number}")

    site = customer_repo.get_site(db, order.site_id)
    invoice = _create(
        db,
        kind=InvoiceKind.ORDER,
        parent={"order_id": order.id},
        customer_id=order.customer_id,
        place_of_supply=site.state,
        lines=lines,
        invoice_date=invoice_date,
        actor=actor,
        meta=meta,
    )
    return invoice, True


def create_for_ticket(
    db: Session,
    ticket: SupportTicket,
    *,
    actor: User,
    meta: RequestMeta | None = None,
    invoice_date: date | None = None,
) -> Invoice:
    """Service invoice for a paid repair (parts + labour). Does not commit."""
    existing = invoice_repo.get_by_ticket(db, ticket.id)
    if existing is not None:
        return existing

    charges = ticket_repo.charges(db, ticket.id)
    products = ticket_repo.products(db, [c.product_id for c in charges if c.product_id])
    lines = []
    for charge in charges:
        product = products.get(charge.product_id) if charge.product_id else None
        rate = charge.gst_rate
        if rate is None:  # rows billed before the snapshot column existed
            rate = product.gst_rate if product else settings.service_labour_gst_percent
        taxable = money(charge.quantity * charge.customer_price)
        lines.append(
            {
                "description_snapshot": charge.description
                or (product.name if product else str(charge.charge_type).title()),
                "sku": product.sku if product and charge.charge_type == ChargeType.PART else None,
                "quantity": charge.quantity,
                "unit_price": charge.customer_price,
                "gst_rate": rate,
                "taxable": taxable,
                "gst_amount": money(taxable * rate / HUNDRED),
            }
        )
    site = customer_repo.get_site(db, ticket.site_id)
    return _create(
        db,
        kind=InvoiceKind.SERVICE,
        parent={"ticket_id": ticket.id},
        customer_id=ticket.customer_id,
        place_of_supply=site.state,
        lines=lines,
        invoice_date=invoice_date,
        actor=actor,
        meta=meta,
    )


def create_for_order_now(
    db: Session, order_id: int, *, actor: User, meta: RequestMeta | None = None
) -> tuple[Invoice, bool]:
    """POST /orders/{id}/invoice: backfill for orders delivered before invoices existed."""
    order = order_repo.get_by_id_for_update(db, order_id)
    if order is None:
        raise NotFound("Order not found")
    if order.status not in INVOICEABLE_ORDER_STATUSES:
        raise OrderNotDelivered(
            f"An invoice is created once the order is delivered (current status: {order.status})"
        )
    invoice, created = create_for_order(db, order, actor=actor, meta=meta)
    if created:
        db.commit()
        db.refresh(invoice)
    return invoice, created


# ---------------------------------------------------------------- Read side

def get_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = invoice_repo.get(db, invoice_id)
    if invoice is None:
        raise NotFound("Invoice not found")
    return invoice


def to_read(db: Session, invoice: Invoice) -> InvoiceRead:
    customer = customer_repo.get_by_id(db, invoice.customer_id)
    order = order_repo.get_by_id(db, invoice.order_id) if invoice.order_id else None
    ticket = ticket_repo.get(db, invoice.ticket_id) if invoice.ticket_id else None
    site = customer_repo.get_site(db, order.site_id if order else ticket.site_id)
    paid = balance = None
    if order is not None:
        paid = money(payment_repo.sum_completed(db, order.id))
        balance = money(invoice.total - paid)
    return InvoiceRead(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        kind=invoice.kind,
        status=invoice.status,
        financial_year=invoice.financial_year,
        invoice_date=invoice.issued_on,
        place_of_supply=invoice.place_of_supply_state,
        seller=InvoiceSeller(
            name=settings.company_name,
            gstin=settings.company_gstin,
            address=settings.company_address,
            state=settings.company_state,
        ),
        buyer=InvoiceBuyer(
            customer_id=customer.id,
            name=customer.full_name,
            phone=customer.phone_e164,
            email=customer.email,
            gstin=customer.gstin,
            address=QuoteSite.model_validate(site, from_attributes=True),
        ),
        order_id=invoice.order_id,
        order_number=order.order_number if order else None,
        ticket_id=invoice.ticket_id,
        ticket_number=ticket.ticket_number if ticket else None,
        lines=[
            InvoiceLineRead(
                description=line.description_snapshot,
                sku=line.sku,
                qty=line.quantity,
                unit_price=line.unit_price,
                gst_percent=line.gst_rate,
                taxable=line.taxable,
                gst_amount=line.gst_amount,
            )
            for line in invoice_repo.list_lines(db, invoice.id)
        ],
        taxable_amount=invoice.subtotal,
        cgst=invoice.cgst,
        sgst=invoice.sgst,
        igst=invoice.igst,
        gst_total=invoice.tax_total,
        total=invoice.total,
        amount_paid=paid,
        balance_due=balance,
        created_at=invoice.created_at,
    )


def list_invoices(
    db: Session,
    *,
    kind: InvoiceKind | None = None,
    first: date | None = None,
    last: date | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[InvoiceSummary], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    rows, total = invoice_repo.list_page(
        db,
        kind=kind,
        first=first,
        last=last,
        search=(search or "").strip() or None,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return [
        InvoiceSummary(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            kind=invoice.kind,
            invoice_date=invoice.issued_on,
            customer_name=customer.full_name,
            order_id=invoice.order_id,
            ticket_id=invoice.ticket_id,
            taxable_amount=invoice.subtotal,
            gst_total=invoice.tax_total,
            total=invoice.total,
        )
        for invoice, customer in rows
    ], total


# ---------------------------------------------------------------- Internal helpers

def _sums(lines: list[dict[str, Any]]) -> tuple[Decimal, Decimal]:
    taxable = sum((line["taxable"] for line in lines), Decimal("0.00"))
    gst = sum((line["gst_amount"] for line in lines), Decimal("0.00"))
    return money(taxable), money(gst)


def _create(
    db: Session,
    *,
    kind: InvoiceKind,
    parent: dict[str, int],
    customer_id: int,
    place_of_supply: str,
    lines: list[dict[str, Any]],
    invoice_date: date | None,
    actor: User,
    meta: RequestMeta | None,
) -> Invoice:
    day = invoice_date or today_ist()
    fy = financial_year(day)
    number = format_number(fy, invoice_repo.next_number(db, fy))
    taxable, gst = _sums(lines)
    cgst, sgst, igst = split_gst(gst, place_of_supply)
    invoice = invoice_repo.create(
        db,
        {
            **parent,
            "kind": kind,
            "customer_id": customer_id,
            "invoice_number": number,
            "financial_year": fy,
            "status": InvoiceStatus.ISSUED,
            "issued_on": day,
            "place_of_supply_state": place_of_supply,
            "subtotal": taxable,
            "tax_total": gst,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "total": money(taxable + gst),
            "created_by": actor.id,
        },
    )
    invoice_repo.add_lines(db, invoice.id, lines)
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id,
        action="invoice.created",
        entity_type="invoice",
        entity_id=invoice.id,
        old_data=None,
        new_data={
            **parent,
            "invoice_number": number,
            "kind": kind,
            "taxable": str(taxable),
            "cgst": str(cgst),
            "sgst": str(sgst),
            "igst": str(igst),
            "total": str(invoice.total),
        },
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )
    return invoice
