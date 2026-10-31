"""Incoming enquiries, including unqualified website leads."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.core.enums import CustomerType, EnquirySource, EnquiryStatus, SystemType, sql_in


class Enquiry(IdMixin, TimestampMixin, Base):
    __tablename__ = "enquiries"
    __table_args__ = (
        CheckConstraint(sql_in("status", EnquiryStatus), name="status_allowed"),
        CheckConstraint(sql_in("source", EnquirySource), name="source_allowed"),
        CheckConstraint(sql_in("system_type", SystemType), name="system_type_allowed"),
        CheckConstraint(sql_in("customer_type", CustomerType), name="customer_type_allowed"),
        CheckConstraint(
            "site_id IS NULL OR customer_id IS NOT NULL", name="site_requires_customer"
        ),
        CheckConstraint(
            "phone_e164 IS NULL OR phone_e164 ~ '^\\+[1-9][0-9]{7,14}$'", name="phone_e164"
        ),
        CheckConstraint("pincode IS NULL OR pincode ~ '^[0-9]{6}$'", name="pincode_india_format"),
        ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            ondelete="RESTRICT",
            name="fk_enquiry_site_customer_match",
        ),
        UniqueConstraint("id", "site_id", name="uq_enquiries_id_site"),
        Index("ix_enquiries_status_created_at", "status", "created_at"),
        Index("ix_enquiries_phone_e164", "phone_e164"),
        Index(
            "uq_enquiries_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    site_id: Mapped[int | None] = mapped_column(BigInteger)
    contact_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_raw: Mapped[str] = mapped_column(String(40), nullable=False)
    phone_e164: Mapped[str | None] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(255))
    # Retain the submitted address/requirements before a qualified lead gets a Site row.
    address_line: Mapped[str] = mapped_column(String(240), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    requested_capacity_kw: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    system_type: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subsidy_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    shadow_free_roof_area_sqft: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    monthly_bill_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    grid_connection_suitable: Mapped[bool | None] = mapped_column(Boolean)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="website")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="new")
    notes: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    qualified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
