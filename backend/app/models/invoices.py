"""Invoices and their immutable line snapshots."""

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import InvoiceKind, InvoiceStatus, sql_in
from app.db.base import Base, IdMixin, TimestampMixin


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(
            "((order_id IS NOT NULL) <> (ticket_id IS NOT NULL))", name="exactly_one_parent"
        ),
        CheckConstraint(
            "subtotal >= 0 AND tax_total >= 0 AND total >= 0", name="totals_nonnegative"
        ),
        CheckConstraint(sql_in("status", InvoiceStatus), name="status_allowed"),
        CheckConstraint(sql_in("kind", InvoiceKind), name="kind_allowed"),
        CheckConstraint(
            f"(kind = '{InvoiceKind.ORDER.value}') = (order_id IS NOT NULL)",
            name="kind_matches_parent",
        ),
        CheckConstraint("financial_year ~ '^[0-9]{4}-[0-9]{2}$'", name="financial_year_format"),
        CheckConstraint("cgst >= 0 AND sgst >= 0 AND igst >= 0", name="gst_split_nonnegative"),
        CheckConstraint("cgst + sgst + igst = tax_total", name="gst_split_sums"),
        CheckConstraint("subtotal + tax_total = total", name="total_sums"),
        Index("uq_invoices_order_id", "order_id", unique=True),
        Index("uq_invoices_ticket_id", "ticket_id", unique=True),
        Index("ix_invoices_issued_on", "issued_on"),
        Index("ix_invoices_customer_id", "customer_id"),
    )

    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    ticket_id: Mapped[int | None] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="RESTRICT")
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    financial_year: Mapped[str] = mapped_column(String(7), nullable=False)
    place_of_supply_state: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    issued_on: Mapped[date | None] = mapped_column(Date)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    cgst: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    sgst: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    igst: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class InvoiceItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
        CheckConstraint("gst_rate BETWEEN 0 AND 100", name="gst_rate_range"),
        CheckConstraint("taxable >= 0 AND gst_amount >= 0", name="amounts_nonnegative"),
        Index("ix_invoice_items_invoice_id", "invoice_id"),
    )

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    description_snapshot: Mapped[str] = mapped_column(String(240), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(60))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    taxable: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class InvoiceSequence(TimestampMixin, Base):
    """One row per Indian financial year; locked FOR UPDATE to hand out the next number."""

    __tablename__ = "invoice_sequences"
    __table_args__ = (CheckConstraint("last_number >= 0", name="last_number_nonnegative"),)

    financial_year: Mapped[str] = mapped_column(String(7), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
