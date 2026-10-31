"""Government subsidy applications associated with a customer site and order."""

from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import SubsidyStatus, sql_in


class SubsidyApplication(IdMixin, TimestampMixin, Base):
    __tablename__ = "subsidy_applications"
    __table_args__ = (
        CheckConstraint(sql_in("status", SubsidyStatus), name="status_allowed"),
        CheckConstraint(
            "requested_amount >= 0 AND (approved_amount IS NULL OR approved_amount >= 0)",
            name="amounts_nonnegative",
        ),
        CheckConstraint(
            "approved_amount IS NULL OR approved_amount <= requested_amount",
            name="approved_not_above_requested",
        ),
        ForeignKeyConstraint(
            ["site_id", "customer_id"],
            ["sites.id", "sites.customer_id"],
            ondelete="RESTRICT",
            name="fk_subsidy_site_customer_match",
        ),
        Index("ix_subsidy_applications_customer_status", "customer_id", "status"),
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    scheme_name: Mapped[str] = mapped_column(String(180), nullable=False)
    application_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    documents: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
