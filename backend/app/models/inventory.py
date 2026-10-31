"""Inventory balances, immutable stock movements, and serialized units."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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

from app.db.base import Base, IdMixin, TimestampMixin
from app.core.enums import SerialUnitStatus, StockMovementReason, sql_in


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
        Index("ix_serialized_units_serial_number", "serial_number"),
        Index("ix_serialized_units_product_status", "product_id", "status"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    serial_number: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="in_stock")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
