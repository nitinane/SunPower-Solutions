"""
Orders and payments: the first payment starts the warehouse and the crew.

Flow: quote accepted -> order PENDING_PAYMENT -> first payment -> CONFIRMED
      + pick list (dispatch in its first status) + installation job (planned, unscheduled).
Rules enforced here:
- Only pending_payment / confirmed orders take payments (409 ORDER_NOT_PAYABLE).
- Same Idempotency-Key -> the first payment is returned, nothing new is created.
- Never more than the balance due (409 OVERPAYMENT). Paid amounts are SQL SUMs, never stored.
- The server picks the payment kind: first == total -> full, first < total -> advance,
  later -> balance.
- One pick list and one installation job per order (checked here, DB unique as backup).
Every change is written to audit_log in the same transaction.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import (
    DispatchStatus,
    InstallationJobStatus,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    PaymentType,
)
from app.exceptions import BusinessRuleViolation, Conflict, NotFound, ValidationFailed
from app.models.orders import Order
from app.models.payments import Payment
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import customers as customer_repo
from app.repositories import orders as order_repo
from app.repositories import payments as payment_repo
from app.repositories import quotes as quote_repo
from app.schemas.orders import (
    InstallationJobRef,
    OrderLine,
    OrderRead,
    OrderSummary,
    PaymentCreate,
    PaymentRead,
    PickListRef,
)
from app.schemas.quotes import QuoteCustomer, QuoteSite
from app.services import subsidies as subsidy_service
from app.services.catalog import money, price_line
from app.services.common import RequestMeta

MAX_PAGE_SIZE = 100
BUSINESS_TZ = ZoneInfo("Asia/Kolkata")
PAYABLE_STATUSES = frozenset({OrderStatus.PENDING_PAYMENT, OrderStatus.CONFIRMED})
PICK_LIST_FIRST_STATUS = DispatchStatus.DRAFT  # spec "PICK" (docs/decisions.md)
JOB_FIRST_STATUS = InstallationJobStatus.PLANNED  # unscheduled; crew assigned in P2-1


class OrderNotPayable(BusinessRuleViolation):
    code = "ORDER_NOT_PAYABLE"


class Overpayment(BusinessRuleViolation):
    code = "OVERPAYMENT"


class DuplicatePaymentReference(Conflict):
    code = "DUPLICATE_PAYMENT_REFERENCE"


class IdempotencyKeyReused(Conflict):
    code = "IDEMPOTENCY_KEY_REUSED"


@dataclass(frozen=True)
class PaymentOutcome:
    payment: Payment
    order: Order
    created: bool


# ---------------------------------------------------------------- Read side

def get_order(db: Session, order_id: int) -> Order:
    order = order_repo.get_by_id(db, order_id)
    if order is None:
        raise NotFound("Order not found")
    return order


def to_read(db: Session, order: Order) -> OrderRead:
    customer = customer_repo.get_by_id(db, order.customer_id)
    site = customer_repo.get_site(db, order.site_id)
    quote = quote_repo.get_by_id(db, order.quote_id)
    items = [
        OrderLine(
            id=item.id,
            product_id=item.product_id,
            sku=item.sku_snapshot,
            name=item.product_name_snapshot,
            qty=item.quantity,
            unit_price=item.unit_price,
            line_total=price_line(
                product_id=item.product_id,
                sku=item.sku_snapshot,
                name=item.product_name_snapshot,
                qty=item.quantity,
                unit_price=item.unit_price,
                gst_percent=item.gst_rate,
            ).line_total,
            requires_serial=requires_serial,
        )
        for item, requires_serial in order_repo.list_items_with_serial_flag(db, order.id)
    ]
    paid = money(payment_repo.sum_completed(db, order.id))
    pick_list = order_repo.get_pick_list(db, order.id)
    job = order_repo.get_installation_job(db, order.id)
    return OrderRead(
        id=order.id,
        order_number=order.order_number,
        quote_id=order.quote_id,
        status=order.status,
        customer=QuoteCustomer(
            id=customer.id, name=customer.full_name, phone=customer.phone_e164,
            email=customer.email,
        ),
        site=QuoteSite(
            id=site.id,
            address_line1=site.address_line1,
            address_line2=site.address_line2,
            city=site.city,
            state=site.state,
            pincode=site.pincode,
        ),
        items=items,
        subtotal=money(quote.subtotal),
        gst=money(quote.tax_total),
        total=money(quote.total),
        amount_paid=paid,
        balance_due=money(quote.total - paid),
        payments=[
            PaymentRead.model_validate(p) for p in payment_repo.list_for_order(db, order.id)
        ],
        pick_list=PickListRef(
            id=pick_list.id, dispatch_number=pick_list.dispatch_number, status=pick_list.status
        ) if pick_list else None,
        installation_job=(
            InstallationJobRef(
                id=job.id,
                status=job.status,
                scheduled_date=(
                    job.scheduled_at.astimezone(BUSINESS_TZ).date() if job.scheduled_at else None
                ),
            )
            if job
            else None
        ),
        confirmed_at=order.confirmed_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def list_orders(
    db: Session,
    *,
    status: OrderStatus | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OrderSummary], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    rows, total = order_repo.list_page(
        db,
        status=status,
        search=(search or "").strip() or None,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    items = []
    for order, customer, order_total, paid in rows:
        order_total, paid = money(Decimal(order_total)), money(Decimal(paid))
        items.append(
            OrderSummary(
                id=order.id,
                order_number=order.order_number,
                status=order.status,
                customer_name=customer.full_name,
                customer_phone=customer.phone_e164,
                total=order_total,
                amount_paid=paid,
                balance_due=money(order_total - paid),
                created_at=order.created_at,
            )
        )
    return items, total


# ---------------------------------------------------------------- Workflow actions

def record_payment(
    db: Session,
    order_id: int,
    data: PaymentCreate,
    *,
    actor: User,
    idempotency_key: str | None = None,
    meta: RequestMeta | None = None,
) -> PaymentOutcome:
    """Record money received. The first payment confirms the order and starts the work."""
    if data.method != PaymentMethod.CASH and data.reference is None:
        raise ValidationFailed(
            "Reference is required", fields={"reference": "Required unless the method is cash"}
        )

    # 1. Lock the order and check it can take money.
    order = order_repo.get_by_id_for_update(db, order_id)
    if order is None:
        raise NotFound("Order not found")
    if order.status not in PAYABLE_STATUSES:
        raise OrderNotPayable(
            f"This order cannot take payments (current status: {order.status})"
        )

    # 2. Same key -> same payment.
    if idempotency_key:
        existing = payment_repo.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            if existing.order_id != order.id:
                raise IdempotencyKeyReused("This idempotency key belongs to another payment")
            return PaymentOutcome(existing, order, created=False)

    # 3. Never more than the balance.
    quote = quote_repo.get_by_id(db, order.quote_id)
    order_total = money(quote.total)
    paid = money(payment_repo.sum_completed(db, order.id))
    balance = money(order_total - paid)
    amount = money(data.amount)
    if amount > balance:
        raise Overpayment(
            f"Payment of ₹{amount} is more than the balance due of ₹{balance}",
            fields={"amount": f"At most ₹{balance}"},
        )

    # 4. Server decides the kind.
    is_first = payment_repo.count_completed(db, order.id) == 0
    if not is_first:
        kind = PaymentType.BALANCE
    elif amount == order_total:
        kind = PaymentType.FULL
    else:
        kind = PaymentType.ADVANCE

    # 5. Insert (duplicate reference -> 409, nothing saved).
    try:
        payment = payment_repo.create(
            db,
            {
                "order_id": order.id,
                "amount": amount,
                "payment_type": kind,
                "method": data.method,
                "status": PaymentStatus.COMPLETED,
                "reference_number": data.reference,
                "idempotency_key": idempotency_key or f"auto-{uuid4().hex}",
                "recorded_by": actor.id,
                "paid_at": data.paid_at or _now(),
            },
        )
    except IntegrityError as exc:
        db.rollback()
        if idempotency_key:
            existing = payment_repo.get_by_idempotency_key(db, idempotency_key)
            if existing is not None:
                if existing.order_id != order_id:
                    raise IdempotencyKeyReused(
                        "This idempotency key belongs to another payment"
                    ) from None
                return PaymentOutcome(existing, get_order(db, order_id), created=False)
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) != (
            "uq_payments_reference_number"
        ):
            raise
        raise DuplicatePaymentReference(
            "A payment with this reference is already recorded",
            fields={"reference": "Already used"},
        ) from None

    _audit(db, actor, "payment.recorded", "payment", payment.id, None, _payment_snapshot(payment),
           meta)

    # 6. First payment: confirm + pick list + installation job.
    if is_first:
        _confirm_and_start_work(db, order, actor, meta)
        subsidy_service.create_on_first_payment(db, order, actor=actor, meta=meta)

    db.commit()
    db.refresh(payment)
    db.refresh(order)
    return PaymentOutcome(payment, order, created=True)


# ---------------------------------------------------------------- Internal helpers

def _confirm_and_start_work(
    db: Session, order: Order, actor: User, meta: RequestMeta | None
) -> None:
    if order.status == OrderStatus.PENDING_PAYMENT:
        old_status = order.status
        order_repo.update(db, order, {"status": OrderStatus.CONFIRMED, "confirmed_at": _now()})
        _audit(
            db, actor, "order.confirmed", "order", order.id,
            {"status": old_status},
            {"status": order.status, "confirmed_at": _json_safe(order.confirmed_at)},
            meta,
        )

    if order_repo.get_pick_list(db, order.id) is None:
        pick_list = order_repo.create_pick_list(
            db,
            {
                "order_id": order.id,
                "dispatch_number": f"DSP-TMP-{uuid4().hex[:20]}",
                "status": PICK_LIST_FIRST_STATUS,
            },
        )
        order_repo.update_pick_list(db, pick_list, {"dispatch_number": f"DSP-{pick_list.id:06d}"})
        _audit(
            db, actor, "pick_list.created", "dispatch", pick_list.id, None,
            {"order_id": order.id, "dispatch_number": pick_list.dispatch_number,
             "status": pick_list.status},
            meta,
        )

    if order_repo.get_installation_job(db, order.id) is None:
        job = order_repo.create_installation_job(
            db,
            {
                "order_id": order.id,
                "site_id": order.site_id,
                "status": JOB_FIRST_STATUS,
                "created_by": actor.id,
            },
        )
        _audit(
            db, actor, "installation_job.created", "installation_job", job.id, None,
            {"order_id": order.id, "status": job.status},
            meta,
        )


def _now() -> datetime:
    return datetime.now(UTC)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(money(value))
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _payment_snapshot(payment: Payment) -> dict[str, Any]:
    fields = ("order_id", "amount", "payment_type", "method", "reference_number", "paid_at")
    return {field: _json_safe(getattr(payment, field)) for field in fields}


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
