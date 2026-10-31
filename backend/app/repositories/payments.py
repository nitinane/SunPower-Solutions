"""Payment queries. No commits and no business rules here."""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import PaymentStatus
from app.models.payments import Payment


def get_by_idempotency_key(db: Session, key: str) -> Payment | None:
    return db.scalars(select(Payment).where(Payment.idempotency_key == key)).first()


def create(db: Session, data: dict[str, Any]) -> Payment:
    payment = Payment(**data)
    db.add(payment)
    db.flush()
    return payment


def list_for_order(db: Session, order_id: int) -> list[Payment]:
    stmt = (
        select(Payment)
        .where(Payment.order_id == order_id)
        .order_by(Payment.created_at, Payment.id)
    )
    return list(db.scalars(stmt))


def count_completed(db: Session, order_id: int) -> int:
    stmt = select(func.count()).where(
        Payment.order_id == order_id, Payment.status == PaymentStatus.COMPLETED
    )
    return db.scalar(stmt) or 0


def sum_completed(db: Session, order_id: int) -> Decimal:
    """Amount paid so far, computed with SQL SUM (never stored)."""
    stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.order_id == order_id, Payment.status == PaymentStatus.COMPLETED
    )
    return Decimal(db.scalar(stmt) or 0)
