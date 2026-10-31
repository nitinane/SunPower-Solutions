"""Warranty records for serialized units and bulk non-serialized products."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Warranty(IdMixin, TimestampMixin, Base):
    __tablename__ = "warranties"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "serialized_unit_id IS NULL OR quantity = 1", name="serialized_quantity_one"
        ),
        CheckConstraint("end_date >= start_date", name="date_range_valid"),
        ForeignKeyConstraint(
            ["order_item_id", "order_id", "product_id"],
            ["order_items.id", "order_items.order_id", "order_items.product_id"],
            ondelete="RESTRICT",
            name="fk_warranty_order_line_product",
        ),
        ForeignKeyConstraint(
            ["serialized_unit_id", "product_id"],
            ["serialized_units.id", "serialized_units.product_id"],
            ondelete="RESTRICT",
            name="fk_warranty_serial_product",
        ),
        Index(
            "uq_warranties_serial_unit",
            "serialized_unit_id",
            unique=True,
            postgresql_where=text("serialized_unit_id IS NOT NULL"),
        ),
        Index(
            "uq_warranties_bulk_order_item",
            "order_item_id",
            unique=True,
            postgresql_where=text("serialized_unit_id IS NULL"),
        ),
        Index("ix_warranties_end_date", "end_date"),
    )

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    serialized_unit_id: Mapped[int | None] = mapped_column(BigInteger)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, server_default="1")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
