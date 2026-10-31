"""Government subsidy applications associated with a customer site and order."""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import SubsidyDocType, SubsidyStatus, sql_in
from app.db.base import Base, IdMixin, TimestampMixin


class SubsidyApplication(IdMixin, TimestampMixin, Base):
    __tablename__ = "subsidy_applications"
    __table_args__ = (
        CheckConstraint(sql_in("status", SubsidyStatus), name="status_allowed"),
        CheckConstraint(
            "requested_amount >= 0 AND (approved_amount IS NULL OR approved_amount >= 0)",
            name="amounts_nonnegative",
        ),
        CheckConstraint(
            "disbursed_amount IS NULL OR "
            "(disbursed_amount > 0 AND approved_amount IS NOT NULL "
            "AND disbursed_amount <= approved_amount)",
            name="disbursed_within_sanctioned",
        ),
        ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            ondelete="RESTRICT",
            name="fk_subsidy_site_customer_match",
        ),
        UniqueConstraint("order_id", name="uq_subsidy_applications_order_id"),
        Index("ix_subsidy_applications_customer_status", "customer_id", "status"),
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    scheme_name: Mapped[str] = mapped_column(String(180), nullable=False)
    application_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    requested_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    # Spec "sanctioned_amount" (docs/decisions.md).
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    documents: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    applied_on: Mapped[date | None] = mapped_column(Date)
    inspected_on: Mapped[date | None] = mapped_column(Date)
    sanctioned_on: Mapped[date | None] = mapped_column(Date)
    disbursed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    disbursed_on: Mapped[date | None] = mapped_column(Date)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class SubsidyDocument(IdMixin, TimestampMixin, Base):
    """One checklist row per required document. Never stores ID numbers."""

    __tablename__ = "subsidy_documents"
    __table_args__ = (
        UniqueConstraint("application_id", "doc_type", name="uq_subsidy_documents_app_doc"),
        CheckConstraint(sql_in("doc_type", SubsidyDocType), name="doc_type_allowed"),
    )

    application_id: Mapped[int] = mapped_column(
        ForeignKey("subsidy_applications.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(40), nullable=False)
    received: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    received_on: Mapped[date | None] = mapped_column(Date)
    storage_key: Mapped[str | None] = mapped_column(String(500), unique=True)
    content_type: Mapped[str | None] = mapped_column(String(100))
