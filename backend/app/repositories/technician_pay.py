"""Monthly pay run queries. No commits and no business rules here."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.enums import ChargeType, InstallationJobStatus
from app.models.installations import InstallationJob, JobTechnician
from app.models.orders import Order
from app.models.service_tickets import SupportTicket, TicketCharge
from app.models.technician_pay import PayRun, PayRunLine
from app.models.users import User


def lock_or_create_run(db: Session, month: str, created_by: int) -> tuple[PayRun, bool]:
    """Insert the month's run if missing (race-safe), then lock it. Returns (run, created)."""
    inserted = db.execute(
        insert(PayRun)
        .values(month=month, created_by=created_by)
        .on_conflict_do_nothing(index_elements=["month"])
        .returning(PayRun.id)
    ).scalar()
    stmt = (
        select(PayRun)
        .where(PayRun.month == month)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).one(), inserted is not None


def get_run(db: Session, run_id: int, *, lock: bool = False) -> PayRun | None:
    stmt = select(PayRun).where(PayRun.id == run_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    return db.scalars(stmt).first()


def get_run_by_month(db: Session, month: str) -> PayRun | None:
    return db.scalars(select(PayRun).where(PayRun.month == month)).first()


def update_run(db: Session, run: PayRun, data: dict[str, Any]) -> PayRun:
    for field, value in data.items():
        setattr(run, field, value)
    db.flush()
    return run


def replace_lines(db: Session, run_id: int, rows: list[dict[str, Any]]) -> None:
    db.execute(delete(PayRunLine).where(PayRunLine.pay_run_id == run_id))
    db.add_all(PayRunLine(pay_run_id=run_id, **row) for row in rows)
    db.flush()


def list_runs(db: Session, *, limit: int, offset: int) -> tuple[list[tuple], int]:
    """(run, technician count, total amount), newest month first."""
    stmt = (
        select(
            PayRun,
            func.count(PayRunLine.id),
            func.coalesce(func.sum(PayRunLine.amount), Decimal("0")),
        )
        .outerjoin(PayRunLine, PayRunLine.pay_run_id == PayRun.id)
        .group_by(PayRun.id)
        .order_by(PayRun.month.desc())
        .limit(limit)
        .offset(offset)
    )
    total = db.scalar(select(func.count(PayRun.id))) or 0
    return [tuple(row) for row in db.execute(stmt).all()], total


def list_lines(
    db: Session, run_id: int, technician_id: int | None = None
) -> list[tuple[PayRunLine, str]]:
    stmt = (
        select(PayRunLine, User.full_name)
        .join(User, User.id == PayRunLine.technician_id)
        .where(PayRunLine.pay_run_id == run_id)
        .order_by(User.full_name, User.id)
    )
    if technician_id is not None:
        stmt = stmt.where(PayRunLine.technician_id == technician_id)
    return [tuple(row) for row in db.execute(stmt).all()]


# ---------------------------------------------------------------- Month totals (GROUP BY)

def _install_filter(start: datetime, end: datetime):
    return (
        InstallationJob.status == InstallationJobStatus.COMPLETED,
        InstallationJob.completed_at >= start,
        InstallationJob.completed_at < end,
    )


def _repair_filter(start: datetime, end: datetime):
    # One labour charge row per resolved visit, written at resolve time.
    return (
        TicketCharge.charge_type == ChargeType.LABOUR,
        TicketCharge.created_at >= start,
        TicketCharge.created_at < end,
        SupportTicket.assigned_to.is_not(None),
    )


def install_totals(
    db: Session, start: datetime, end: datetime
) -> list[tuple[int, Decimal, Decimal]]:
    """(technician_id, hours, amount) where amount = SUM(ROUND(hours x snapshot rate, 2))."""
    stmt = (
        select(
            JobTechnician.technician_id,
            func.sum(JobTechnician.hours_worked),
            func.sum(func.round(JobTechnician.hours_worked * JobTechnician.hourly_rate, 2)),
        )
        .join(InstallationJob, InstallationJob.id == JobTechnician.job_id)
        .where(*_install_filter(start, end))
        .group_by(JobTechnician.technician_id)
    )
    return [tuple(row) for row in db.execute(stmt).all()]


def repair_totals(
    db: Session, start: datetime, end: datetime
) -> list[tuple[int, Decimal, Decimal]]:
    """(technician_id, hours, current hourly rate)."""
    stmt = (
        select(
            SupportTicket.assigned_to,
            func.sum(TicketCharge.quantity),
            func.coalesce(User.hourly_rate, Decimal("0")),
        )
        .join(SupportTicket, SupportTicket.id == TicketCharge.ticket_id)
        .join(User, User.id == SupportTicket.assigned_to)
        .where(*_repair_filter(start, end))
        .group_by(SupportTicket.assigned_to, User.hourly_rate)
    )
    return [tuple(row) for row in db.execute(stmt).all()]


def current_rates(db: Session, user_ids: list[int]) -> dict[int, Decimal]:
    if not user_ids:
        return {}
    stmt = select(User.id, func.coalesce(User.hourly_rate, Decimal("0"))).where(
        User.id.in_(user_ids)
    )
    return {row[0]: row[1] for row in db.execute(stmt).all()}


# ---------------------------------------------------------------- Breakdown

def install_breakdown(
    db: Session, start: datetime, end: datetime, technician_id: int | None = None
) -> list[tuple]:
    """(technician_id, job_id, order_number, hours, hourly_rate)."""
    stmt = (
        select(
            JobTechnician.technician_id,
            InstallationJob.id,
            Order.order_number,
            JobTechnician.hours_worked,
            JobTechnician.hourly_rate,
        )
        .join(InstallationJob, InstallationJob.id == JobTechnician.job_id)
        .join(Order, Order.id == InstallationJob.order_id)
        .where(*_install_filter(start, end))
        .order_by(InstallationJob.completed_at, InstallationJob.id)
    )
    if technician_id is not None:
        stmt = stmt.where(JobTechnician.technician_id == technician_id)
    return [tuple(row) for row in db.execute(stmt).all()]


def repair_breakdown(
    db: Session, start: datetime, end: datetime, technician_id: int | None = None
) -> list[tuple]:
    """(technician_id, ticket_id, ticket_number, hours) per ticket."""
    stmt = (
        select(
            SupportTicket.assigned_to,
            SupportTicket.id,
            SupportTicket.ticket_number,
            func.sum(TicketCharge.quantity),
        )
        .join(SupportTicket, SupportTicket.id == TicketCharge.ticket_id)
        .where(*_repair_filter(start, end))
        .group_by(SupportTicket.assigned_to, SupportTicket.id, SupportTicket.ticket_number)
        .order_by(SupportTicket.id)
    )
    if technician_id is not None:
        stmt = stmt.where(SupportTicket.assigned_to == technician_id)
    return [tuple(row) for row in db.execute(stmt).all()]
