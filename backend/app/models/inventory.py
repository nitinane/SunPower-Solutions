"""Inventory balances, immutable stock movements, and serialized units."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import SerialUnitStatus, StockMovementReason, sql_in
from app.db.base import Base, IdMixin, TimestampMixin


class Inventory(IdMixin, TimestampMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity_on_hand >= 0", name="on_hand_nonnegative"),
        CheckConstraint("quantity_reserved >= 0", name="reserved_nonnegative"),
        CheckConstraint("quantity_reserved <= quantity_on_hand", name="reserved_not_above_on_hand"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    quantity_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )
    quantity_reserved: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default="0"
    )


class StockMovement(IdMixin, Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity_delta <> 0", name="quantity_delta_nonzero"),
        CheckConstraint(sql_in("reason", StockMovementReason), name="reason_allowed"),
        CheckConstraint(
            "(reference_type IS NULL) = (reference_id IS NULL)", name="reference_pair"
        ),
        Index("ix_stock_movements_reference", "reference_type", "reference_id"),
        Index("ix_stock_movements_product_created", "product_id", "created_at"),
        Index(
            "uq_stock_movements_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    performed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SerializedUnit(IdMixin, TimestampMixin, Base):
    __tablename__ = "serialized_units"
    __table_args__ = (
        CheckConstraint(
            "serial_number = upper(btrim(serial_number)) AND length(serial_number) > 0",
            name="serial_normalized",
        ),
        CheckConstraint(sql_in("status", SerialUnitStatus), name="status_allowed"),
        UniqueConstraint("product_id", "serial_number", name="uq_serialized_units_product_serial"),
        UniqueConstraint("id", "product_id", name="uq_serialized_units_id_product"),
        Index("ix_serialized_units_serial_number", "serial_number", unique=True),
        Index("ix_serialized_units_product_status", "product_id", "status"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    serial_number: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="in_stock")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StockReceipt(IdMixin, TimestampMixin, Base):
    """Goods received from a supplier (RCV-{id:06d})."""

    __tablename__ = "stock_receipts"
    __table_args__ = (Index("ix_stock_receipts_received_on", "received_on"),)

    receipt_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(180), nullable=False)
    supplier_invoice_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class StockReceiptLine(IdMixin, Base):
    __tablename__ = "stock_receipt_lines"
    __table_args__ = (
        CheckConstraint("qty > 0", name="qty_positive"),
        CheckConstraint("unit_cost > 0", name="unit_cost_positive"),
        Index("ix_stock_receipt_lines_receipt_id", "receipt_id"),
    )

    receipt_id: Mapped[int] = mapped_column(
        ForeignKey("stock_receipts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
