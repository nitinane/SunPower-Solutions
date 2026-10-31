"""Monthly technician pay: SQL totals, IST month bounds, draft recalculation, paid lock."""

import random
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_quotes import _user
from test_subsidies import _paid_order

from app.core.dates import BUSINESS_TZ
from app.core.enums import ChargeType, InstallationJobStatus, UserRole
from app.models.installations import InstallationJob, JobTechnician
from app.models.orders import Order
from app.models.service_tickets import SupportTicket, TicketCharge
from app.services.technician_pay import month_bounds

pytest_plugins = ["test_quotes"]


@pytest.fixture
def year():
    # Tests share the dev DB until P3-1: a random far-future year keeps months unique.
    return random.randint(3000, 9999)


@pytest.fixture
def director(db, api):
    return api(_user(db, UserRole.DIRECTOR))


def _tech(db, rate):
    user = _user(db, UserRole.TECHNICIAN)
    user.hourly_rate = Decimal(rate)
    db.commit()
    return user


def _finished_job(db, client, finished_at, crew):
    """crew: [(technician, hours, rate snapshot)]"""
    order_id = _paid_order(db, client, subsidy=False)
    job = db.scalars(select(InstallationJob).where(InstallationJob.order_id == order_id)).one()
    job.status = InstallationJobStatus.COMPLETED
    job.started_at = finished_at
    job.completed_at = finished_at
    for tech, hours, rate in crew:
        db.add(JobTechnician(job_id=job.id, technician_id=tech.id,
                             hours_worked=Decimal(hours), hourly_rate=Decimal(rate)))
    db.commit()
    return job


def _repair(db, order_id, tech, hours, resolved_at):
    order = db.get(Order, order_id)
    ticket = SupportTicket(
        ticket_number=f"TKT-T-{uuid4().hex[:12]}", customer_id=order.customer_id,
        site_id=order.site_id, issue_description="No power", status="resolved",
        assigned_to=tech.id, resolved_at=resolved_at, labour_hours=Decimal(hours),
    )
    db.add(ticket)
    db.flush()
    db.add(TicketCharge(ticket_id=ticket.id, charge_type=ChargeType.LABOUR,
                        quantity=Decimal(hours), customer_price=Decimal("0"),
                        created_at=resolved_at))
    db.commit()
    return ticket


def _ist(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=BUSINESS_TZ)


def _line(run, tech):
    return next(line for line in run["lines"] if line["technician_id"] == tech.id)


def test_month_bounds_are_ist():
    start, end = month_bounds("2026-10")
    assert start == datetime(2026, 9, 30, 18, 30, tzinfo=UTC)
    assert end == datetime(2026, 10, 31, 18, 30, tzinfo=UTC)


def test_exact_amount_two_jobs_one_repair_and_ist_month(db, api, office, director, year):
    client = api(office)
    tech, other = _tech(db, "250.00"), _tech(db, "200.00")
    job1 = _finished_job(db, client, _ist(year, 10, 5, 15, 0),
                         [(tech, "3.25", "250.00"), (other, "3.25", "200.00")])
    # Finished 23:30 IST on the 31st (18:00 UTC): October, not November.
    job2 = _finished_job(db, client, _ist(year, 10, 31, 23, 30), [(tech, "2.50", "300.00")])
    # Finished 01:00 IST on Nov 1 (still Oct 31 in UTC): November, not October.
    _finished_job(db, client, _ist(year, 11, 1, 1, 0), [(tech, "4.00", "250.00")])
    tech.hourly_rate = Decimal("333.33")  # current rate, used for repairs only
    db.commit()
    ticket = _repair(db, job1.order_id, tech, "1.75", _ist(year, 10, 20, 11, 0))

    response = director.post("/api/v1/pay-runs", json={"month": f"{year}-10"})
    assert response.status_code == 201, response.text
    run = response.json()
    line = _line(run, tech)
    assert line["install_hours"] == "5.75"
    assert line["install_amount"] == "1562.50"   # 3.25 x 250 + 2.50 x 300
    assert line["repair_hours"] == "1.75"
    assert line["repair_amount"] == "583.33"     # 1.75 x 333.33 = 583.3275
    assert line["amount"] == "2145.83"
    assert line["rate"] == "333.33"
    assert {j["job_id"] for j in line["jobs"]} == {job1.id, job2.id}
    assert [t["ticket_number"] for t in line["tickets"]] == [ticket.ticket_number]
    assert _line(run, other)["amount"] == "650.00"
    assert run["total_amount"] == "2795.83"

    november = director.post("/api/v1/pay-runs", json={"month": f"{year}-11"}).json()
    assert _line(november, tech)["install_hours"] == "4.00"
    assert _line(november, tech)["amount"] == "1000.00"


def test_recalculation_replaces_lines_and_paid_run_is_locked(db, api, office, director, year):
    client = api(office)
    tech = _tech(db, "100.00")
    _finished_job(db, client, _ist(year, 3, 10, 10, 0), [(tech, "2.00", "100.00")])
    first = director.post("/api/v1/pay-runs", json={"month": f"{year}-03"})
    assert first.status_code == 201
    assert _line(first.json(), tech)["amount"] == "200.00"

    _finished_job(db, client, _ist(year, 3, 11, 10, 0), [(tech, "1.00", "100.00")])
    again = director.post("/api/v1/pay-runs", json={"month": f"{year}-03"})
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]
    assert len(again.json()["lines"]) == 1
    assert _line(again.json(), tech)["amount"] == "300.00"

    run_id = first.json()["id"]
    paid = director.post(f"/api/v1/pay-runs/{run_id}/mark-paid",
                         json={"paid_on": f"{year}-04-01", "payment_reference": "NEFT-1"})
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    locked = director.post("/api/v1/pay-runs", json={"month": f"{year}-03"})
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "PAY_RUN_LOCKED"
    again_paid = director.post(f"/api/v1/pay-runs/{run_id}/mark-paid",
                               json={"paid_on": f"{year}-04-01", "payment_reference": "X"})
    assert again_paid.json()["error"]["code"] == "PAY_RUN_LOCKED"

    listed = director.get("/api/v1/pay-runs", params={"page_size": 100})
    assert listed.status_code == 200
    assert director.get(f"/api/v1/pay-runs/{run_id}").json()["total_amount"] == "300.00"


def test_technician_sees_only_own_pay_and_non_director_403(db, api, office, director, year):
    client = api(office)
    tech, other = _tech(db, "100.00"), _tech(db, "150.00")
    _finished_job(db, client, _ist(year, 6, 1, 9, 0),
                  [(tech, "1.00", "100.00"), (other, "2.00", "150.00")])
    run = director.post("/api/v1/pay-runs", json={"month": f"{year}-06"}).json()

    mine = api(tech).get("/api/v1/me/pay", params={"month": f"{year}-06"})
    assert mine.status_code == 200, mine.text
    assert mine.json()["line"]["technician_id"] == tech.id
    assert mine.json()["line"]["amount"] == "100.00"
    assert all(j["amount"] == "100.00" for j in mine.json()["line"]["jobs"])
    assert api(tech).get("/api/v1/me/pay", params={"month": f"{year}-07"}).status_code == 404

    tech_client = api(tech)
    assert tech_client.get("/api/v1/pay-runs").status_code == 403
    assert tech_client.get(f"/api/v1/pay-runs/{run['id']}").status_code == 403
    assert client.post("/api/v1/pay-runs", json={"month": f"{year}-06"}).status_code == 403
    bad = director.post("/api/v1/pay-runs", json={"month": f"{year}-13"})
    assert bad.status_code == 422
