"""Technician pay: legacy per-job payouts, and monthly pay runs (P2-3)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import PayoutStatus, sql_in
from app.db.base import Base, IdMixin, TimestampMixin


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


class PayRun(IdMixin, TimestampMixin, Base):
    """One monthly technician pay run. Status: pending (spec "draft") -> paid."""

    __tablename__ = "pay_runs"
    __table_args__ = (
        CheckConstraint(sql_in("status", PayoutStatus), name="status_allowed"),
        CheckConstraint("month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name="month_format"),
        CheckConstraint(
            "status <> 'paid' OR (paid_on IS NOT NULL AND payment_reference IS NOT NULL)",
            name="paid_has_details",
        ),
    )

    month: Mapped[str] = mapped_column(CHAR(7), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    paid_on: Mapped[date | None] = mapped_column(Date)
    payment_reference: Mapped[str | None] = mapped_column(String(100))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class PayRunLine(IdMixin, TimestampMixin, Base):
    __tablename__ = "pay_run_lines"
    __table_args__ = (
        UniqueConstraint("pay_run_id", "technician_id", name="uq_pay_run_lines_run_technician"),
        CheckConstraint(
            "install_hours >= 0 AND repair_hours >= 0 AND rate >= 0 AND amount >= 0",
            name="values_nonnegative",
        ),
        Index("ix_pay_run_lines_technician_id", "technician_id"),
    )

    pay_run_id: Mapped[int] = mapped_column(
        ForeignKey("pay_runs.id", ondelete="CASCADE"), nullable=False
    )
    technician_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    install_hours: Mapped[Decimal] = mapped_column(
        Numeric(9, 2), nullable=False, server_default="0"
    )
    repair_hours: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False, server_default="0")
    # Technician's current hourly rate (used for repair hours); install hours use job snapshots.
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, server_default="0")
    install_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    repair_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
