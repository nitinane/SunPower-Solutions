"""Confirmed orders and copied quote line snapshots."""

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.core.enums import OrderStatus, sql_in


class Order(IdMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(sql_in("status", OrderStatus), name="status_allowed"),
        ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            ondelete="RESTRICT",
            name="fk_order_site_customer_match",
        ),
        UniqueConstraint("id", "site_id", name="uq_orders_id_site"),
        UniqueConstraint("id", "quote_id", name="uq_orders_id_quote"),
        Index("ix_orders_customer_created_at", "customer_id", "created_at"),
    )

    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="pending_payment"
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class OrderItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0 AND unit_cost >= 0", name="prices_nonnegative"),
        CheckConstraint("gst_rate BETWEEN 0 AND 100", name="gst_rate_range"),
        CheckConstraint("warranty_months_snapshot >= 0", name="warranty_months_nonnegative"),
        ForeignKeyConstraint(
            ["order_id", "quote_id"],
            ["orders.id", "orders.quote_id"],
            ondelete="CASCADE",
            name="fk_order_item_order_quote_match",
        ),
        ForeignKeyConstraint(
            ["quote_item_id", "quote_id", "product_id"],
            ["quote_items.id", "quote_items.quote_id", "quote_items.product_id"],
            ondelete="RESTRICT",
            name="fk_order_item_quote_product_match",
        ),
        UniqueConstraint("id", "order_id", "product_id", name="uq_order_items_id_order_product"),
        Index("ix_order_items_order_id", "order_id"),
    )

    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quote_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quote_item_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    sku_snapshot: Mapped[str] = mapped_column(String(60), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    warranty_months_snapshot: Mapped[int] = mapped_column(nullable=False, server_default="0")
