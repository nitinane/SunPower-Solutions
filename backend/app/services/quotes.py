"""
Quotes from package templates; accepting a quote creates the order.

Flow: approved survey -> DRAFT (parts list copied from the package, prices frozen)
      -> SENT -> ACCEPTED (order created, waiting for payment) | REJECTED (reason required)
Rules enforced here:
- No quote without an approved survey (409 SURVEY_NOT_APPROVED); package must be active.
- Every line snapshots sku, name, sale price, cost price, GST% and warranty, so later catalog
  price changes never touch an existing quote or order.
- Accept: one order per quote (409 if one exists); every other open quote of the same
  enquiry is cancelled in the same transaction.
Every change is written to audit_log in the same transaction.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.enums import OrderStatus, QuoteStatus, SurveyStatus
from app.exceptions import BusinessRuleViolation, Conflict, NotFound
from app.models.quotes import Quote, QuoteItem
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import catalog as catalog_repo
from app.repositories import customers as customer_repo
from app.repositories import enquiries as enquiry_repo
from app.repositories import orders as order_repo
from app.repositories import quotes as quote_repo
from app.repositories import surveys as survey_repo
from app.schemas.catalog import PriceLine
from app.schemas.quotes import QuoteCreate, QuoteCustomer, QuoteRead, QuoteReject, QuoteSite
from app.services.catalog import money, price_line, totals
from app.services.common import RequestMeta

INSTALLATION_SKU = "SVC-INSTALL"
MAX_PAGE_SIZE = 100

AUDIT_FIELDS = ("status", "package_id", "subtotal", "tax_total", "total")


class SurveyNotApproved(BusinessRuleViolation):
    code = "SURVEY_NOT_APPROVED"


class PackageNotAvailable(BusinessRuleViolation):
    code = "PACKAGE_NOT_AVAILABLE"


class QuoteStatusInvalid(BusinessRuleViolation):
    code = "QUOTE_STATUS_INVALID"


class OrderAlreadyExists(Conflict):
    code = "ORDER_ALREADY_EXISTS"


# ---------------------------------------------------------------- Read side

def to_read(db: Session, quote: Quote) -> QuoteRead:
    """Printable quote: customer, site, frozen lines and totals."""
    survey = survey_repo.get_by_id(db, quote.survey_id)
    site = customer_repo.get_site(db, survey.site_id)
    enquiry = enquiry_repo.get_by_id(db, quote.enquiry_id)
    customer = customer_repo.get_by_id(db, site.customer_id)
    lines = [_item_line(item) for item in quote_repo.list_items(db, quote.id)]
    return QuoteRead(
        id=quote.id,
        quote_number=quote.quote_number,
        enquiry_id=quote.enquiry_id,
        survey_id=quote.survey_id,
        package_id=quote.package_id,
        status=quote.status,
        customer=QuoteCustomer(
            id=customer.id if customer else None,
            name=customer.full_name if customer else enquiry.contact_name,
            phone=customer.phone_e164 if customer else enquiry.phone_e164,
            email=customer.email if customer else enquiry.email,
        ),
        site=QuoteSite(
            id=site.id,
            address_line1=site.address_line1,
            address_line2=site.address_line2,
            city=site.city,
            state=site.state,
            pincode=site.pincode,
        ),
        lines=lines,
        subtotal=quote.subtotal,
        gst=quote.tax_total,
        total=quote.total,
        notes=quote.terms,
        valid_until=quote.valid_until,
        created_at=quote.created_at,
        updated_at=quote.updated_at,
    )


def get_quote(db: Session, quote_id: int) -> Quote:
    quote = quote_repo.get_by_id(db, quote_id)
    if quote is None:
        raise NotFound("Quote not found")
    return quote


def list_quotes(
    db: Session,
    *,
    status: QuoteStatus | None = None,
    enquiry_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Quote], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return quote_repo.list_page(
        db, status=status, enquiry_id=enquiry_id, limit=page_size, offset=(page - 1) * page_size
    )


# ---------------------------------------------------------------- Workflow actions

def create_quote(
    db: Session, data: QuoteCreate, *, actor: User, meta: RequestMeta | None = None
) -> Quote:
    """Copy the package parts list into a DRAFT quote with frozen prices."""
    survey = survey_repo.get_by_id_for_update(db, data.survey_id)
    if survey is None:
        raise NotFound("Survey not found")
    if survey.status != SurveyStatus.APPROVED:
        raise SurveyNotApproved(
            f"A quote can only be made after the site survey is approved "
            f"(current status: {survey.status})"
        )

    package = catalog_repo.get_package(db, data.package_id)
    if package is None or not package.is_active:
        raise PackageNotAvailable("This package is not available")

    sources = [
        (product, component.quantity)
        for component, product in catalog_repo.list_components(db, [package.id])
    ]
    if data.include_installation:
        service = catalog_repo.get_product_by_sku(db, INSTALLATION_SKU)
        if service is None or not service.is_active:
            raise PackageNotAvailable("Installation service is not available")
        sources.append((service, package.system_capacity_kw))

    quote = quote_repo.create(
        db,
        {
            "enquiry_id": survey.enquiry_id,
            "survey_id": survey.id,
            "package_id": package.id,
            "quote_number": f"QT-TMP-{uuid4().hex[:20]}",
            "status": QuoteStatus.DRAFT,
            "created_by": actor.id,
            "terms": data.notes,
        },
    )
    lines: list[PriceLine] = []
    for product, qty in sources:
        quote_repo.add_item(
            db,
            {
                "quote_id": quote.id,
                "product_id": product.id,
                "sku_snapshot": product.sku,
                "product_name_snapshot": product.name,
                "description_snapshot": product.description,
                "quantity": qty,
                "unit_price": product.sale_price,
                "unit_cost": product.cost_price,
                "gst_rate": product.gst_rate,
                "warranty_months_snapshot": product.warranty_months,
            },
        )
        lines.append(
            price_line(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                qty=qty,
                unit_price=product.sale_price,
                gst_percent=product.gst_rate,
            )
        )

    subtotal, gst, total = totals(lines)
    quote_repo.update(
        db,
        quote,
        {
            "quote_number": f"QT-{quote.id:06d}",
            "subtotal": subtotal,
            "tax_total": gst,
            "total": total,
        },
    )
    _audit(db, actor, "quote.created", "quote", quote.id, None, _snapshot(quote), meta)
    db.commit()
    db.refresh(quote)
    return quote


def send_quote(
    db: Session, quote_id: int, *, actor: User, meta: RequestMeta | None = None
) -> Quote:
    quote = _get_for_update(db, quote_id)
    _require_status(quote, QuoteStatus.DRAFT, "Only a draft quote can be sent")
    old = _snapshot(quote)
    quote_repo.update(db, quote, {"status": QuoteStatus.SENT})
    _audit(db, actor, "quote.sent", "quote", quote.id, old, _snapshot(quote), meta)
    db.commit()
    db.refresh(quote)
    return quote


def reject_quote(
    db: Session,
    quote_id: int,
    data: QuoteReject,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> Quote:
    quote = _get_for_update(db, quote_id)
    _require_status(quote, QuoteStatus.SENT, "Only a sent quote can be rejected")
    old = _snapshot(quote)
    quote_repo.update(db, quote, {"status": QuoteStatus.REJECTED})
    new = {**_snapshot(quote), "reason": data.reason}
    _audit(db, actor, "quote.rejected", "quote", quote.id, old, new, meta)
    db.commit()
    db.refresh(quote)
    return quote


def accept_quote(
    db: Session, quote_id: int, *, actor: User, meta: RequestMeta | None = None
) -> tuple[Quote, int]:
    """Customer said yes: create the order (waiting for payment) from the frozen lines."""
    quote = _get_for_update(db, quote_id)
    if order_repo.get_by_quote_id(db, quote.id) is not None:
        raise OrderAlreadyExists("An order already exists for this quote")
    _require_status(quote, QuoteStatus.SENT, "Only a sent quote can be accepted")

    old = _snapshot(quote)
    quote_repo.update(db, quote, {"status": QuoteStatus.ACCEPTED})

    survey = survey_repo.get_by_id(db, quote.survey_id)
    site = customer_repo.get_site(db, survey.site_id)
    order = order_repo.create(
        db,
        {
            "quote_id": quote.id,
            "customer_id": site.customer_id,
            "site_id": site.id,
            "order_number": f"ORD-TMP-{uuid4().hex[:20]}",
            "status": OrderStatus.PENDING_PAYMENT,
            "created_by": actor.id,
        },
    )
    order_repo.update(db, order, {"order_number": f"ORD-{order.id:06d}"})
    items = quote_repo.list_items(db, quote.id)
    for item in items:
        order_repo.add_item(
            db,
            {
                "order_id": order.id,
                "quote_id": quote.id,
                "quote_item_id": item.id,
                "product_id": item.product_id,
                "sku_snapshot": item.sku_snapshot,
                "product_name_snapshot": item.product_name_snapshot,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "unit_cost": item.unit_cost,
                "gst_rate": item.gst_rate,
                "warranty_months_snapshot": item.warranty_months_snapshot,
            },
        )

    for other in quote_repo.list_open_for_enquiry_for_update(
        db, quote.enquiry_id, exclude_id=quote.id
    ):
        other_old = _snapshot(other)
        quote_repo.update(db, other, {"status": QuoteStatus.CANCELLED})
        _audit(
            db,
            actor,
            "quote.cancelled",
            "quote",
            other.id,
            other_old,
            {**_snapshot(other), "reason": "another quote was accepted"},
            meta,
        )

    _audit(db, actor, "quote.accepted", "quote", quote.id, old, _snapshot(quote), meta)
    _audit(
        db,
        actor,
        "order.created",
        "order",
        order.id,
        None,
        {
            "order_number": order.order_number,
            "quote_id": quote.id,
            "status": order.status,
            "items": len(items),
            "subtotal": str(quote.subtotal),
            "gst": str(quote.tax_total),
            "total": str(quote.total),
        },
        meta,
    )
    db.commit()
    db.refresh(quote)
    return quote, order.id


# ---------------------------------------------------------------- Internal helpers

def _item_line(item: QuoteItem) -> PriceLine:
    return price_line(
        product_id=item.product_id,
        sku=item.sku_snapshot,
        name=item.product_name_snapshot,
        qty=item.quantity,
        unit_price=item.unit_price,
        gst_percent=item.gst_rate,
    )


def _get_for_update(db: Session, quote_id: int) -> Quote:
    quote = quote_repo.get_by_id_for_update(db, quote_id)
    if quote is None:
        raise NotFound("Quote not found")
    return quote


def _require_status(quote: Quote, expected: QuoteStatus, message: str) -> None:
    if quote.status != expected:
        raise QuoteStatusInvalid(f"{message} (current status: {quote.status})")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(money(value))
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _snapshot(quote: Quote) -> dict[str, Any]:
    return {field: _json_safe(getattr(quote, field, None)) for field in AUDIT_FIELDS}


def _audit(
    db: Session,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: int,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
    meta: RequestMeta | None,
) -> None:
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
