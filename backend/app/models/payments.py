"""Payments against exactly one order or service ticket."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import PaymentMethod, PaymentStatus, PaymentType, sql_in
from app.db.base import Base, IdMixin, TimestampMixin


class Payment(IdMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "((order_id IS NOT NULL) <> (ticket_id IS NOT NULL))", name="exactly_one_parent"
        ),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(sql_in("method", PaymentMethod), name="method_allowed"),
        CheckConstraint(sql_in("status", PaymentStatus), name="status_allowed"),
        CheckConstraint(sql_in("payment_type", PaymentType), name="payment_type_allowed"),
        Index("uq_payments_idempotency_key", "idempotency_key", unique=True),
        Index("ix_payments_order_id", "order_id"),
        Index("ix_payments_ticket_id", "ticket_id"),
    )

    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    ticket_id: Mapped[int | None] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="RESTRICT")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="completed")
    reference_number: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
