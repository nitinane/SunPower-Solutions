"""Installation jobs, technician assignments, and private evidence metadata."""

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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.models.enums import EvidenceContentType, EvidenceType, InstallationStatus, sql_in


class InstallationJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "installation_jobs"
    __table_args__ = (
        CheckConstraint(sql_in("status", InstallationStatus), name="status_allowed"),
        ForeignKeyConstraint(
            ["order_id", "site_id"],
            ["orders.id", "orders.site_id"],
            ondelete="RESTRICT",
            name="fk_job_order_site_match",
        ),
        Index("ix_installation_jobs_scheduled_status", "scheduled_at", "status"),
    )

    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    site_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="planned")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    completion_notes: Mapped[str | None] = mapped_column(Text)
    installed_capacity_kw: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    power_test_passed: Mapped[bool | None] = mapped_column(Boolean)
    signed_by_name: Mapped[str | None] = mapped_column(String(150))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobTechnician(IdMixin, TimestampMixin, Base):
    __tablename__ = "job_technicians"
    __table_args__ = (
        UniqueConstraint("job_id", "technician_id", name="uq_job_technician"),
        CheckConstraint("hours_worked >= 0", name="hours_worked_nonnegative"),
        CheckConstraint("hourly_rate >= 0", name="hourly_rate_nonnegative"),
        Index("ix_job_technicians_technician_id", "technician_id"),
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("installation_jobs.id", ondelete="CASCADE"), nullable=False
    )
    technician_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    hours_worked: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False, server_default="0")
    # Rate is copied from users.hourly_rate when this assignment is created.
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)


class InstallationEvidence(IdMixin, TimestampMixin, Base):
    __tablename__ = "installation_evidence"
    __table_args__ = (
        CheckConstraint(sql_in("evidence_type", EvidenceType), name="evidence_type_allowed"),
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760", name="file_size_limit_10mb"
        ),
        CheckConstraint(sql_in("content_type", EvidenceContentType), name="content_type_allowed"),
        Index("ix_installation_evidence_job_type", "job_id", "evidence_type"),
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("installation_jobs.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(String(240))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
