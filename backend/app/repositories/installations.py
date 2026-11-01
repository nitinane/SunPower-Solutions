"""Installation job, crew and evidence queries. No commits and no business rules here."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.enums import InstallationJobStatus, TicketStatus
from app.models.customers import Customer, Site
from app.models.installations import InstallationEvidence, InstallationJob, JobTechnician
from app.models.orders import Order
from app.models.service_tickets import SupportTicket
from app.models.surveys import SiteSurvey
from app.models.users import User


def get_job(db: Session, job_id: int, *, lock: bool = False) -> InstallationJob | None:
    stmt = select(InstallationJob).where(InstallationJob.id == job_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalars(stmt).first()


def update_job(db: Session, job: InstallationJob, data: dict[str, Any]) -> InstallationJob:
    for field, value in data.items():
        setattr(job, field, value)
    db.flush()
    return job


# ---------------------------------------------------------------- Crew

def lock_users(db: Session, user_ids: list[int]) -> list[User]:
    """Lock technician rows in id order so two schedulers can't double-book one person."""
    stmt = select(User).where(User.id.in_(user_ids)).order_by(User.id).with_for_update()
    return list(db.scalars(stmt))


def list_crew(db: Session, job_ids: list[int]) -> list[tuple[JobTechnician, User]]:
    if not job_ids:
        return []
    stmt = (
        select(JobTechnician, User)
        .join(User, User.id == JobTechnician.technician_id)
        .where(JobTechnician.job_id.in_(job_ids))
        .order_by(JobTechnician.job_id, User.full_name, User.id)
    )
    return [tuple(row) for row in db.execute(stmt).all()]


def crew_rows_for_update(db: Session, job_id: int) -> list[JobTechnician]:
    stmt = select(JobTechnician).where(JobTechnician.job_id == job_id).with_for_update()
    return list(db.scalars(stmt))


def is_on_crew(db: Session, job_id: int, user_id: int) -> bool:
    stmt = select(JobTechnician.id).where(
        JobTechnician.job_id == job_id, JobTechnician.technician_id == user_id
    )
    return db.scalar(stmt) is not None


def replace_crew(db: Session, job_id: int, rows: list[dict[str, Any]]) -> None:
    db.execute(delete(JobTechnician).where(JobTechnician.job_id == job_id))
    db.add_all(JobTechnician(job_id=job_id, **row) for row in rows)
    db.flush()


def find_double_bookings(
    db: Session,
    technician_ids: list[int],
    start: datetime,
    end: datetime,
    *,
    exclude_job_id: int,
) -> list[tuple[str, str, datetime]]:
    """(technician name, order number, scheduled_at) of clashing active jobs that day."""
    stmt = (
        select(User.full_name, Order.order_number, InstallationJob.scheduled_at)
        .select_from(JobTechnician)
        .join(InstallationJob, InstallationJob.id == JobTechnician.job_id)
        .join(Order, Order.id == InstallationJob.order_id)
        .join(User, User.id == JobTechnician.technician_id)
        .where(
            JobTechnician.technician_id.in_(technician_ids),
            InstallationJob.id != exclude_job_id,
            InstallationJob.status.in_(
                [InstallationJobStatus.SCHEDULED, InstallationJobStatus.IN_PROGRESS]
            ),
            InstallationJob.scheduled_at >= start,
            InstallationJob.scheduled_at < end,
        )
        .order_by(User.full_name)
    )
    return [tuple(row) for row in db.execute(stmt).all()]


# ---------------------------------------------------------------- Schedule views

def _job_rows():
    return (
        select(InstallationJob, Order, Customer, Site)
        .join(Order, Order.id == InstallationJob.order_id)
        .join(Customer, Customer.id == Order.customer_id)
        .join(Site, Site.id == InstallationJob.site_id)
    )


def schedule_page(
    db: Session, start: datetime, end: datetime, *, limit: int, offset: int
) -> tuple[list[tuple[InstallationJob, Order, Customer, Site]], int]:
    stmt = _job_rows().where(
        InstallationJob.scheduled_at >= start,
        InstallationJob.scheduled_at < end,
        InstallationJob.status != InstallationJobStatus.CANCELLED,
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(InstallationJob.scheduled_at, InstallationJob.id).limit(limit).offset(offset)
    ).all()
    return [tuple(row) for row in rows], total


def job_with_order(
    db: Session, job_id: int
) -> tuple[InstallationJob, Order, Customer, Site] | None:
    row = db.execute(_job_rows().where(InstallationJob.id == job_id)).first()
    return tuple(row) if row else None


def jobs_for_technician(
    db: Session, user_id: int, start: datetime, end: datetime
) -> list[tuple[InstallationJob, Order, Customer, Site]]:
    stmt = (
        _job_rows()
        .join(JobTechnician, JobTechnician.job_id == InstallationJob.id)
        .where(
            JobTechnician.technician_id == user_id,
            InstallationJob.scheduled_at >= start,
            InstallationJob.scheduled_at < end,
            InstallationJob.status != InstallationJobStatus.CANCELLED,
        )
        .order_by(InstallationJob.scheduled_at, InstallationJob.id)
    )
    return [tuple(row) for row in db.execute(stmt).all()]


def surveys_for_user(
    db: Session, user_id: int, start: datetime, end: datetime
) -> list[tuple[SiteSurvey, Customer, Site]]:
    stmt = (
        select(SiteSurvey, Customer, Site)
        .join(Site, Site.id == SiteSurvey.site_id)
        .join(Customer, Customer.id == Site.customer_id)
        .where(
            SiteSurvey.surveyor_id == user_id,
            SiteSurvey.scheduled_at >= start,
            SiteSurvey.scheduled_at < end,
        )
        .order_by(SiteSurvey.scheduled_at, SiteSurvey.id)
    )
    return [tuple(row) for row in db.execute(stmt).all()]


def ticket_visits_for_user(
    db: Session, user_id: int, day: date
) -> list[tuple[SupportTicket, Customer, Site]]:
    stmt = (
        select(SupportTicket, Customer, Site)
        .join(Customer, Customer.id == SupportTicket.customer_id)
        .join(Site, Site.id == SupportTicket.site_id)
        .where(
            SupportTicket.assigned_to == user_id,
            SupportTicket.visit_date == day,
            SupportTicket.status.not_in([TicketStatus.CLOSED, TicketStatus.CANCELLED]),
        )
        .order_by(SupportTicket.id)
    )
    return [tuple(row) for row in db.execute(stmt).all()]


# ---------------------------------------------------------------- Evidence

def count_evidence(db: Session, job_id: int, evidence_type: str) -> int:
    stmt = select(func.count()).where(
        InstallationEvidence.job_id == job_id,
        InstallationEvidence.evidence_type == evidence_type,
    )
    return db.scalar(stmt) or 0


def evidence_ids(db: Session, job_id: int, evidence_type: str) -> list[int]:
    stmt = (
        select(InstallationEvidence.id)
        .where(
            InstallationEvidence.job_id == job_id,
            InstallationEvidence.evidence_type == evidence_type,
        )
        .order_by(InstallationEvidence.id)
    )
    return list(db.scalars(stmt))


def add_evidence(db: Session, data: dict[str, Any]) -> InstallationEvidence:
    evidence = InstallationEvidence(**data)
    db.add(evidence)
    db.flush()
    return evidence


def get_evidence(db: Session, evidence_id: int) -> InstallationEvidence | None:
    return db.get(InstallationEvidence, evidence_id)


def jobs_page(db: Session, status: InstallationJobStatus, *, limit: int, offset: int):
    stmt = _job_rows().where(InstallationJob.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(InstallationJob.id).limit(limit).offset(offset)).all()
    return [tuple(row) for row in rows], total
