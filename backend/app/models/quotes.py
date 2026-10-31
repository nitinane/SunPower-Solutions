"""Quotes and immutable product/price snapshots."""

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import QuoteStatus, sql_in
from app.db.base import Base, IdMixin, TimestampMixin


class Quote(IdMixin, TimestampMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        CheckConstraint(sql_in("status", QuoteStatus), name="status_allowed"),
        CheckConstraint(
            "subtotal >= 0 AND tax_total >= 0 AND discount_total >= 0 AND total >= 0",
            name="totals_nonnegative",
        ),
        ForeignKeyConstraint(
            ["survey_id", "enquiry_id"],
            ["site_surveys.id", "site_surveys.enquiry_id"],
            ondelete="RESTRICT",
            name="fk_quote_survey_same_enquiry",
        ),
        Index("ix_quotes_enquiry_status", "enquiry_id", "status"),
    )

    enquiry_id: Mapped[int] = mapped_column(
        ForeignKey("enquiries.id", ondelete="RESTRICT"), nullable=False
    )
    survey_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    package_id: Mapped[int | None] = mapped_column(
        ForeignKey("solar_packages.id", ondelete="SET NULL")
    )
    quote_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    valid_until: Mapped[date | None] = mapped_column(Date)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    discount_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    terms: Mapped[str | None] = mapped_column(Text)


class QuoteItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "quote_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0 AND unit_cost >= 0", name="prices_nonnegative"),
        CheckConstraint("gst_rate BETWEEN 0 AND 100", name="gst_rate_range"),
        CheckConstraint("warranty_months_snapshot >= 0", name="warranty_months_nonnegative"),
        UniqueConstraint("id", "quote_id", "product_id", name="uq_quote_items_id_quote_product"),
        Index("ix_quote_items_quote_id", "quote_id"),
    )

    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    sku_snapshot: Mapped[str] = mapped_column(String(60), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(180), nullable=False)
    description_snapshot: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    warranty_months_snapshot: Mapped[int] = mapped_column(nullable=False, server_default="0")
