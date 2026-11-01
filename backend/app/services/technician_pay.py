"""
Monthly technician pay.

Rules enforced here:
- A month is [1st 00:00, next 1st 00:00) in Asia/Kolkata.
- Install pay = job_technicians.hours_worked x that row's hourly_rate snapshot, for jobs
  completed in the month. Repair pay = labour hours of repair visits resolved in the month
  by the assigned technician x their current hourly_rate. Totals come from SQL GROUP BY.
- A draft (pending) run is recalculated by replacing its lines; a paid run is locked
  (409 PAY_RUN_LOCKED). Each job/visit falls in exactly one month, so nothing is paid twice.
Every change is written to audit_log in the same transaction.
"""

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.dates import add_months, ist_day_start
from app.core.enums import PayoutStatus
from app.exceptions import BusinessRuleViolation, NotFound
from app.models.technician_pay import PayRun, PayRunLine
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import technician_pay as repo
from app.schemas.technician_pay import (
    JobHours,
    MyPay,
    PayLine,
    PayRunCreate,
    PayRunMarkPaid,
    PayRunRead,
    PayRunSummary,
    TicketHours,
)
from app.services.catalog import money
from app.services.common import RequestMeta

MAX_PAGE_SIZE = 100
ZERO = Decimal("0.00")


class PayRunLocked(BusinessRuleViolation):
    code = "PAY_RUN_LOCKED"


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """'2026-10' -> (2026-10-01 00:00 IST, 2026-11-01 00:00 IST) as UTC timestamps."""
    year, mon = (int(part) for part in month.split("-"))
    first = date(year, mon, 1)
    return ist_day_start(first), ist_day_start(add_months(first, 1))


# ---------------------------------------------------------------- Write side

def calculate(
    db: Session, data: PayRunCreate, *, actor: User, meta: RequestMeta | None = None
) -> tuple[PayRun, bool]:
    run, created = repo.lock_or_create_run(db, data.month, actor.id)
    if run.status == PayoutStatus.PAID:
        raise PayRunLocked(f"The pay run for {run.month} is already paid")

    start, end = month_bounds(run.month)
    lines: dict[int, dict] = defaultdict(
        lambda: {"install_hours": ZERO, "install_amount": ZERO, "repair_hours": ZERO,
                 "repair_amount": ZERO, "rate": None}
    )
    for tech_id, hours, amount in repo.install_totals(db, start, end):
        lines[tech_id]["install_hours"] = money(hours)
        lines[tech_id]["install_amount"] = money(amount)
    for tech_id, hours, rate in repo.repair_totals(db, start, end):
        lines[tech_id]["repair_hours"] = money(hours)
        lines[tech_id]["repair_amount"] = money(hours * rate)
        lines[tech_id]["rate"] = money(rate)

    rates = repo.current_rates(db, [t for t, row in lines.items() if row["rate"] is None])
    rows = []
    for tech_id, row in lines.items():
        rate = row["rate"] if row["rate"] is not None else money(rates.get(tech_id, ZERO))
        rows.append({
            **row,
            "technician_id": tech_id,
            "rate": rate,
            "amount": money(row["install_amount"] + row["repair_amount"]),
        })
    repo.replace_lines(db, run.id, rows)

    total = money(sum((r["amount"] for r in rows), ZERO))
    _audit(db, actor, "pay_run.calculated", run.id, None,
           {"month": run.month, "status": run.status, "technicians": len(rows),
            "total": str(total), "created": created}, meta)
    db.commit()
    db.refresh(run)
    return run, created


def mark_paid(
    db: Session, run_id: int, data: PayRunMarkPaid, *, actor: User,
    meta: RequestMeta | None = None,
) -> PayRun:
    run = repo.get_run(db, run_id, lock=True)
    if run is None:
        raise NotFound("Pay run not found")
    if run.status == PayoutStatus.PAID:
        raise PayRunLocked(f"The pay run for {run.month} is already paid")
    old = {"status": run.status}
    repo.update_run(db, run, {"status": PayoutStatus.PAID, "paid_on": data.paid_on,
                              "payment_reference": data.payment_reference.strip()})
    _audit(db, actor, "pay_run.paid", run.id, old,
           {"status": run.status, "paid_on": data.paid_on.isoformat(),
            "payment_reference": run.payment_reference}, meta)
    db.commit()
    db.refresh(run)
    return run


# ---------------------------------------------------------------- Read side

def list_runs(db: Session, *, page: int, page_size: int) -> tuple[list[PayRunSummary], int]:
    page_size = min(page_size, MAX_PAGE_SIZE)
    rows, total = repo.list_runs(db, limit=page_size, offset=(page - 1) * page_size)
    return [_summary(run, count, amount) for run, count, amount in rows], total


def get_run(db: Session, run_id: int) -> PayRunRead:
    run = repo.get_run(db, run_id)
    if run is None:
        raise NotFound("Pay run not found")
    lines = _lines(db, run)
    total = money(sum((line.amount for line in lines), ZERO))
    return PayRunRead(**_summary(run, len(lines), total).model_dump(), lines=lines)


def my_pay(db: Session, month: str, *, actor: User) -> MyPay:
    run = repo.get_run_by_month(db, month)
    if run is None:
        raise NotFound(f"No pay run for {month} yet")
    lines = _lines(db, run, technician_id=actor.id)
    return MyPay(pay_run_id=run.id, month=run.month, status=run.status, paid_on=run.paid_on,
                 line=lines[0] if lines else None)


def _summary(run: PayRun, count: int, total: Decimal) -> PayRunSummary:
    return PayRunSummary(
        id=run.id, month=run.month, status=run.status, paid_on=run.paid_on,
        payment_reference=run.payment_reference, technician_count=count,
        total_amount=money(total),
    )


def _lines(db: Session, run: PayRun, technician_id: int | None = None) -> list[PayLine]:
    start, end = month_bounds(run.month)
    jobs: dict[int, list[JobHours]] = defaultdict(list)
    for tech_id, job_id, order_number, hours, rate in repo.install_breakdown(
        db, start, end, technician_id
    ):
        jobs[tech_id].append(JobHours(job_id=job_id, order_number=order_number, hours=hours,
                                      hourly_rate=rate, amount=money(hours * rate)))
    tickets: dict[int, list[TicketHours]] = defaultdict(list)
    for tech_id, ticket_id, ticket_number, hours in repo.repair_breakdown(
        db, start, end, technician_id
    ):
        tickets[tech_id].append(
            TicketHours(ticket_id=ticket_id, ticket_number=ticket_number, hours=money(hours))
        )
    return [_line(line, name, jobs, tickets) for line, name in
            repo.list_lines(db, run.id, technician_id)]


def _line(line: PayRunLine, name: str, jobs: dict, tickets: dict) -> PayLine:
    return PayLine(
        technician_id=line.technician_id, technician_name=name,
        install_hours=line.install_hours, repair_hours=line.repair_hours, rate=line.rate,
        install_amount=line.install_amount, repair_amount=line.repair_amount,
        amount=line.amount, jobs=jobs.get(line.technician_id, []),
        tickets=tickets.get(line.technician_id, []),
    )


def _audit(db, actor, action, entity_id, old, new, meta) -> None:
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id,
        action=action,
        entity_type="pay_run",
        entity_id=entity_id,
        old_data=old,
        new_data=new,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )
