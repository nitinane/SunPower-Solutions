"""Products, solar packages, and package components."""

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from app.core.enums import PackageType, ProductCategory, sql_in


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("cost_price >= 0", name="cost_price_nonnegative"),
        CheckConstraint("sale_price >= 0", name="sale_price_nonnegative"),
        CheckConstraint("gst_rate BETWEEN 0 AND 100", name="gst_rate_range"),
        CheckConstraint("warranty_months >= 0", name="warranty_months_nonnegative"),
        CheckConstraint(sql_in("category", ProductCategory), name="category_allowed"),
        Index("ix_products_category_active", "category", "is_active"),
    )

    sku: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sale_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    warranty_months: Mapped[int] = mapped_column(nullable=False, server_default="0")
    tracks_serial: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class SolarPackage(IdMixin, TimestampMixin, Base):
    __tablename__ = "solar_packages"
    __table_args__ = (
        CheckConstraint(sql_in("package_type", PackageType), name="package_type_allowed"),
        CheckConstraint("system_capacity_kw > 0", name="capacity_positive"),
        CheckConstraint("base_price >= 0", name="base_price_nonnegative"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    package_type: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    system_capacity_kw: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class PackageComponent(IdMixin, TimestampMixin, Base):
    __tablename__ = "package_components"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        UniqueConstraint("package_id", "product_id", name="uq_package_component_product"),
    )

    package_id: Mapped[int] = mapped_column(
        ForeignKey("solar_packages.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
