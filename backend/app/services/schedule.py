"""
Crew schedule: a manager books a date and a crew for an installation job.

Rules enforced here:
- Only unscheduled (planned) or scheduled jobs can be (re)scheduled (409 JOB_NOT_SCHEDULABLE).
- The date is today or later in Asia/Kolkata (422).
- 1 to 6 crew members, each an active technician (422).
- A technician has at most one scheduled / in-progress job per day (409 TECHNICIAN_DOUBLE_BOOKED).
  Technician rows are locked while checking, so two parallel bookings can't both win.
- The crew's hourly rate is snapshotted when booked; later rate changes don't touch the job.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.dates import ist_date, ist_day_bounds, ist_day_start, today_ist
from app.core.enums import InstallationJobStatus, UserRole
from app.exceptions import BusinessRuleViolation, NotFound, ValidationFailed
from app.models.installations import InstallationJob
from app.models.users import User
from app.repositories import installations as job_repo
from app.schemas.installations import (
    MyToday,
    ScheduleCreate,
    ScheduleRow,
    TodaySurvey,
    TodayTicketVisit,
)
from app.services.common import RequestMeta
from app.services.installations import audit, schedule_rows, site_read, snapshot

MAX_PAGE_SIZE = 100
MAX_RANGE_DAYS = 62
SCHEDULABLE = frozenset({InstallationJobStatus.PLANNED, InstallationJobStatus.SCHEDULED})


class JobNotSchedulable(BusinessRuleViolation):
    code = "JOB_NOT_SCHEDULABLE"


class TechnicianDoubleBooked(BusinessRuleViolation):
    code = "TECHNICIAN_DOUBLE_BOOKED"


def schedule_job(
    db: Session,
    job_id: int,
    data: ScheduleCreate,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> InstallationJob:
    # 1. Lock the job; status + date.
    job = job_repo.get_job(db, job_id, lock=True)
    if job is None:
        raise NotFound("Installation job not found")
    if job.status not in SCHEDULABLE:
        raise JobNotSchedulable(
            f"This job can no longer be scheduled (current status: {job.status})"
        )
    if data.scheduled_date < today_ist():
        raise ValidationFailed(
            "The installation date cannot be in the past",
            fields={"scheduled_date": "Pick today or a later date"},
        )

    # 2. Every crew member is an active technician (rows locked in id order).
    users = {user.id: user for user in job_repo.lock_users(db, data.technician_ids)}
    invalid = [
        str(tid)
        for tid in data.technician_ids
        if tid not in users
        or not users[tid].is_active
        or users[tid].role != UserRole.TECHNICIAN
    ]
    if invalid:
        raise ValidationFailed(
            "Every crew member must be an active technician",
            fields={"technician_ids": f"Not an active technician: {', '.join(invalid)}"},
        )

    # 3. No double booking that day.
    start, end = ist_day_bounds(data.scheduled_date)
    clashes = job_repo.find_double_bookings(
        db, data.technician_ids, start, end, exclude_job_id=job.id
    )
    if clashes:
        name, order_number, when = clashes[0]
        day = ist_date(when)
        raise TechnicianDoubleBooked(
            f"{name} already has {order_number} on {day.day} {day:%b}",
            fields={"technician_ids": f"{name} is already booked that day"},
        )

    # 4. Replace the crew with rate snapshots; job -> scheduled.
    old = {**snapshot(job), "crew": _crew_ids(db, job.id)}
    job_repo.replace_crew(
        db,
        job.id,
        [
            {
                "technician_id": tid,
                "assigned_by": actor.id,
                "hourly_rate": users[tid].hourly_rate or Decimal("0.00"),
            }
            for tid in data.technician_ids
        ],
    )
    job_repo.update_job(
        db,
        job,
        {
            "status": InstallationJobStatus.SCHEDULED,
            "scheduled_at": ist_day_start(data.scheduled_date),
        },
    )
    audit(db, actor, "installation_job.scheduled", "installation_job", job.id, old,
          {**snapshot(job), "crew": list(data.technician_ids)}, meta)
    db.commit()
    db.refresh(job)
    return job


def list_schedule(
    db: Session, *, first: date, last: date, page: int = 1, page_size: int = 50
) -> tuple[list[ScheduleRow], int]:
    if last < first:
        raise ValidationFailed("'to' must be on or after 'from'", fields={"to": "Before 'from'"})
    if last - first > timedelta(days=MAX_RANGE_DAYS):
        raise ValidationFailed(
            f"Pick at most {MAX_RANGE_DAYS} days", fields={"to": "Range too long"}
        )
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    start, end = ist_day_bounds(first, last)
    rows, total = job_repo.schedule_page(
        db, start, end, limit=page_size, offset=(page - 1) * page_size
    )
    return schedule_rows(db, rows), total


def my_today(db: Session, *, actor: User) -> MyToday:
    today = today_ist()
    start, end = ist_day_bounds(today)
    return MyToday(
        date=today,
        surveys=[
            TodaySurvey(
                id=survey.id,
                status=survey.status,
                scheduled_at=survey.scheduled_at,
                customer_name=customer.full_name,
                site=site_read(site),
            )
            for survey, customer, site in job_repo.surveys_for_user(db, actor.id, start, end)
        ],
        installation_jobs=schedule_rows(
            db, job_repo.jobs_for_technician(db, actor.id, start, end)
        ),
        ticket_visits=[
            TodayTicketVisit(
                id=ticket.id,
                ticket_number=ticket.ticket_number,
                status=ticket.status,
                priority=ticket.priority,
                visit_date=ticket.visit_date,
                issue_description=ticket.issue_description,
                customer_name=customer.full_name,
                site=site_read(site),
            )
            for ticket, customer, site in job_repo.ticket_visits_for_user(db, actor.id, today)
        ],
    )


def _crew_ids(db: Session, job_id: int) -> list[int]:
    return [user.id for _, user in job_repo.list_crew(db, [job_id])]
