"""Site survey queries. No commits and no business rules here."""

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.enums import SurveyStatus
from app.models.enquiries import Enquiry
from app.models.surveys import SiteSurvey

OPEN_STATUSES = (SurveyStatus.SCHEDULED, SurveyStatus.SUBMITTED)


def get_by_id(db: Session, survey_id: int) -> SiteSurvey | None:
    return db.get(SiteSurvey, survey_id)


def get_by_id_for_update(db: Session, survey_id: int) -> SiteSurvey | None:
    """SELECT ... FOR UPDATE: locks the row until the service commits or rolls back."""
    stmt = (
        select(SiteSurvey)
        .where(SiteSurvey.id == survey_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).first()


def find_open_for_enquiry(db: Session, enquiry_id: int) -> SiteSurvey | None:
    """A scheduled or submitted survey that is still in progress for this enquiry."""
    stmt = select(SiteSurvey).where(
        SiteSurvey.enquiry_id == enquiry_id, SiteSurvey.status.in_(OPEN_STATUSES)
    )
    return db.scalars(stmt.limit(1)).first()


def create(db: Session, data: dict[str, Any]) -> SiteSurvey:
    survey = SiteSurvey(**data)
    db.add(survey)
    db.flush()
    return survey


def update(db: Session, survey: SiteSurvey, data: dict[str, Any]) -> SiteSurvey:
    for field, value in data.items():
        setattr(survey, field, value)
    db.flush()
    return survey


def list_page(
    db: Session,
    *,
    status: SurveyStatus | None = None,
    surveyor_id: int | None = None,
    enquiry_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[tuple[SiteSurvey, Enquiry]], int]:
    """Surveys with their enquiry (for name/phone/address), earliest visit first."""
    stmt: Select[tuple[SiteSurvey, Enquiry]] = select(SiteSurvey, Enquiry).join(
        Enquiry, Enquiry.id == SiteSurvey.enquiry_id
    )
    if status:
        stmt = stmt.where(SiteSurvey.status == status)
    if surveyor_id is not None:
        stmt = stmt.where(SiteSurvey.surveyor_id == surveyor_id)
    if enquiry_id is not None:
        stmt = stmt.where(SiteSurvey.enquiry_id == enquiry_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(SiteSurvey.scheduled_at.asc().nulls_last(), SiteSurvey.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [(row[0], row[1]) for row in rows], total