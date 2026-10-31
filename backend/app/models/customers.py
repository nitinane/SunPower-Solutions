"""Customer identities and their physical installation sites."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Customer(IdMixin, TimestampMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("length(btrim(full_name)) > 0", name="full_name_not_blank"),
        CheckConstraint("email IS NULL OR email = lower(btrim(email))", name="email_normalized"),
        CheckConstraint("phone_e164 ~ '^\\+[1-9][0-9]{7,14}$'", name="phone_e164"),
        Index("ix_customers_phone_e164", "phone_e164"),
        Index(
            "ix_customers_email_lower",
            text("lower(email)"),
            postgresql_where=text("email IS NOT NULL"),
        ),
    )

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(16), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Site(IdMixin, TimestampMixin, Base):
    __tablename__ = "sites"
    __table_args__ = (
        CheckConstraint("length(btrim(address_line1)) > 0", name="address_not_blank"),
        CheckConstraint("pincode ~ '^[0-9]{6}$'", name="pincode_india_format"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude_range"
        ),
        UniqueConstraint("id", "customer_id", name="uq_sites_id_customer"),
        Index("ix_sites_customer_id", "customer_id"),
        Index("ix_sites_electricity_consumer_number", "electricity_consumer_number"),
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    site_name: Mapped[str | None] = mapped_column(String(120))
    address_line1: Mapped[str] = mapped_column(String(240), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(240))
    locality: Mapped[str | None] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    electricity_consumer_number: Mapped[str | None] = mapped_column(String(80))
