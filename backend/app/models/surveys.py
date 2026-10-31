"""Site survey submissions and their review trail."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.core.enums import (
    RoofDirection,
    SurveyReviewRequiredStatus,
    SurveyStatus,
    sql_in,
    sql_not_in,
)


class SiteSurvey(IdMixin, TimestampMixin, Base):
    __tablename__ = "site_surveys"
    __table_args__ = (
        CheckConstraint(sql_in("status", SurveyStatus), name="status_allowed"),
        CheckConstraint(sql_in("roof_direction", RoofDirection), name="roof_direction_allowed"),
        CheckConstraint(
            "reviewed_by IS NULL OR reviewed_by <> surveyor_id", name="reviewer_not_surveyor"
        ),
        CheckConstraint(
            f"{sql_not_in('status', SurveyReviewRequiredStatus)} OR "
            "(reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL)",
            name="reviewed_status_has_reviewer",
        ),
        ForeignKeyConstraint(
            ["enquiry_id", "site_id"],
            ["enquiries.id", "enquiries.site_id"],
            ondelete="RESTRICT",
            name="fk_survey_enquiry_site",
        ),
        UniqueConstraint("id", "enquiry_id", name="uq_site_surveys_id_enquiry"),
        Index("ix_site_surveys_enquiry_id", "enquiry_id"),
        Index("ix_site_surveys_surveyor_status", "surveyor_id", "status"),
    )

    enquiry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    site_id: Mapped[int] = mapped_column(
        ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False
    )
    surveyor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="scheduled")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    findings: Mapped[str | None] = mapped_column(Text)
    roof_direction: Mapped[str | None] = mapped_column(String(24))
    roof_tilt_deg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    cable_distance_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
