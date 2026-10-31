"""Payments/compensation owed to technicians for installation work."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.core.enums import PayoutStatus, sql_in


class TechnicianPayment(IdMixin, TimestampMixin, Base):
    __tablename__ = "technician_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(sql_in("status", PayoutStatus), name="status_allowed"),
        Index(
            "uq_technician_payments_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index("ix_technician_payments_technician_status", "technician_id", "status"),
    )

    technician_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    installation_job_id: Mapped[int] = mapped_column(
        ForeignKey("installation_jobs.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
