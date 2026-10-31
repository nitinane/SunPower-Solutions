"""Dashboard read models are query projections; only share links are stored."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class DashboardShareLink(IdMixin, TimestampMixin, Base):
    __tablename__ = "dashboard_share_links"
    __table_args__ = (
        CheckConstraint("length(btrim(period)) > 0", name="period_not_blank"),
        Index("ix_dashboard_share_links_expires_at", "expires_at"),
    )

    # Only the SHA-256 hash of the token is stored; the raw token is shown once.
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
