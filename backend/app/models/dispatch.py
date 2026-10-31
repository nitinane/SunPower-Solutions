"""Dispatch headers and scanned dispatch line items."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DispatchStatus, sql_in
from app.db.base import Base, IdMixin, TimestampMixin


class Dispatch(IdMixin, TimestampMixin, Base):
    __tablename__ = "dispatches"
    __table_args__ = (
        CheckConstraint(sql_in("status", DispatchStatus), name="status_allowed"),
        Index("ix_dispatches_order_status", "order_id", "status"),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    dispatch_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    dispatched_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DispatchItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "dispatch_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "serialized_unit_id IS NULL OR quantity = 1", name="serialized_quantity_one"
        ),
        ForeignKeyConstraint(
            ["order_item_id", "product_id"],
            ["order_items.id", "order_items.product_id"],
            ondelete="RESTRICT",
            name="fk_dispatch_item_order_product",
        ),
        ForeignKeyConstraint(
            ["serialized_unit_id", "product_id"],
            ["serialized_units.id", "serialized_units.product_id"],
            ondelete="RESTRICT",
            name="fk_dispatch_item_serial_product",
        ),
        Index(
            "uq_dispatch_serialized_unit",
            "serialized_unit_id",
            unique=True,
            postgresql_where=text("serialized_unit_id IS NOT NULL"),
        ),
        Index(
            "uq_dispatch_bulk_line",
            "dispatch_id",
            "order_item_id",
            unique=True,
            postgresql_where=text("serialized_unit_id IS NULL"),
        ),
        Index("ix_dispatch_items_order_item_id", "order_item_id"),
    )

    dispatch_id: Mapped[int] = mapped_column(
        ForeignKey("dispatches.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    serialized_unit_id: Mapped[int | None] = mapped_column(BigInteger)
