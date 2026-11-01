"""Customer support tickets, charges, and technician work logs."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ChargeType, NonProductChargeType, TicketPriority, TicketStatus, sql_in
from app.db.base import Base, IdMixin, TimestampMixin


class SupportTicket(IdMixin, TimestampMixin, Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint(sql_in("status", TicketStatus), name="status_allowed"),
        CheckConstraint(sql_in("priority", TicketPriority), name="priority_allowed"),
        CheckConstraint(
            "NOT under_warranty OR warranty_id IS NOT NULL", name="warranty_decision_has_warranty"
        ),
        ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            ondelete="RESTRICT",
            name="fk_ticket_site_customer_match",
        ),
        CheckConstraint(
            "labour_hours IS NULL OR labour_hours >= 0", name="labour_hours_nonnegative"
        ),
        CheckConstraint(
            "parts_subtotal >= 0 AND labour_amount >= 0 AND gst >= 0 AND total >= 0",
            name="amounts_nonnegative",
        ),
        Index("ix_support_tickets_customer_status", "customer_id", "status"),
        Index("ix_support_tickets_status", "status"),
        Index("ix_support_tickets_site_id", "site_id"),
        Index(
            "uq_support_tickets_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    ticket_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warranty_id: Mapped[int | None] = mapped_column(
        ForeignKey("warranties.id", ondelete="RESTRICT")
    )
    faulty_serial_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("serialized_units.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="open")
    priority: Mapped[str] = mapped_column(String(12), nullable=False, server_default="normal")
    under_warranty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    issue_description: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fault_code: Mapped[str | None] = mapped_column(String(60))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    customer_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by_name: Mapped[str | None] = mapped_column(String(150))
    order_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT")
    )
    visit_date: Mapped[date | None] = mapped_column(Date)
    work_notes: Mapped[str | None] = mapped_column(Text)
    labour_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    parts_subtotal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    labour_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    gst: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")


class TicketCharge(IdMixin, TimestampMixin, Base):
    __tablename__ = "ticket_charges"
    __table_args__ = (
        CheckConstraint(sql_in("charge_type", ChargeType), name="charge_type_allowed"),
        CheckConstraint("cost_amount >= 0 AND customer_price >= 0", name="amounts_nonnegative"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            f"(charge_type = '{ChargeType.PART.value}' AND product_id IS NOT NULL) OR "
            f"({sql_in('charge_type', NonProductChargeType)} "
            "AND product_id IS NULL AND replacement_unit_id IS NULL)",
            name="charge_type_product_consistency",
        ),
        CheckConstraint(
            "NOT covered_by_warranty OR customer_price = 0",
            name="warranty_covered_no_customer_charge",
        ),
        ForeignKeyConstraint(
            ["replacement_unit_id", "product_id"],
            ["serialized_units.id", "serialized_units.product_id"],
            ondelete="RESTRICT",
            name="fk_ticket_charge_replacement_product",
        ),
        CheckConstraint("gst_rate IS NULL OR gst_rate BETWEEN 0 AND 100", name="gst_rate_range"),
        Index("ix_ticket_charges_ticket_id", "ticket_id"),
    )

    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False
    )
    charge_type: Mapped[str] = mapped_column(String(10), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    replacement_unit_id: Mapped[int | None] = mapped_column(BigInteger)
    description: Mapped[str | None] = mapped_column(String(240))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, server_default="1")
    cost_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    customer_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    covered_by_warranty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # GST % at billing time (NULL on rows written before invoices existed).
    gst_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))


class TicketWorkLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "ticket_work_logs"
    __table_args__ = (
        CheckConstraint("work_minutes >= 0", name="work_minutes_nonnegative"),
        Index("ix_ticket_work_logs_ticket_created", "ticket_id", "created_at"),
    )

    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False
    )
    technician_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    work_notes: Mapped[str] = mapped_column(Text, nullable=False)
    work_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
