"""Crew schedule, installation form, photos, signature (real Postgres)."""

import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from test_dispatch import _scan_all, _send
from test_quotes import _create, _package_id, _survey, _user

from app.core.dates import today_ist
from app.core.enums import PackageType, UserRole
from app.models.installations import InstallationJob, JobTechnician
from app.models.orders import Order
from app.services.installations import PNG_MAGIC, work_hours

pytest_plugins = ["test_dispatch"]

TODAY = today_ist()
PNG = PNG_MAGIC + b"\x00" * 200
SIGNATURE = base64.b64encode(PNG_MAGIC + b"\x01" * 4000).decode()


def _tech(db, rate: str = "250.00"):
    user = _user(db, UserRole.TECHNICIAN)
    user.hourly_rate = Decimal(rate)
    db.commit()
    return user


@pytest.fixture
def manager(db, api):
    return api(_user(db, UserRole.MANAGER))


def _job_id(db, order_id: int) -> int:
    return db.scalars(select(InstallationJob.id).where(InstallationJob.order_id == order_id)).one()


def _new_job(db, api, office) -> int:
    """A fresh paid order (pick list + unscheduled job), material not delivered."""
    client = api(office)
    quote = _create(client, _survey(db).id, _package_id(db, PackageType.PANEL_SET, 1))
    client.post(f"/api/v1/quotes/{quote['id']}/send")
    order_id = client.post(f"/api/v1/quotes/{quote['id']}/accept").json()["order_id"]
    paid = client.post(
        f"/api/v1/orders/{order_id}/payments", json={"amount": "1000.00", "method": "cash"}
    )
    assert paid.status_code == 201, paid.text
    return _job_id(db, order_id)


def _schedule(manager, job_id, techs, day=TODAY):
    return manager.post(
        f"/api/v1/installation-jobs/{job_id}/schedule",
        json={"scheduled_date": day.isoformat(), "technician_ids": [t.id for t in techs]},
    )


def _error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


@pytest.fixture
def delivered(db, warehouse, pick):
    _scan_all(warehouse, pick)
    assert _send(warehouse, pick).status_code == 200
    response = warehouse.post(
        f"/api/v1/dispatches/{pick['id']}/deliver", json={"receiver_name": "Ravi Kumar"}
    )
    assert response.status_code == 200, response.text
    return {**pick, "job_id": _job_id(db, pick["order_id"])}


@pytest.fixture
def started(db, api, manager, delivered):
    """Delivered order, 2-person crew booked today, job started by the first technician."""
    crew = [_tech(db, "250.00"), _tech(db, "300.00")]
    assert _schedule(manager, delivered["job_id"], crew).status_code == 200
    tech = api(crew[0])
    response = tech.post(f"/api/v1/installation-jobs/{delivered['job_id']}/start")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in_progress"
    return {**delivered, "crew": crew, "tech": tech}


def _photo(client, job_id, content=PNG, name="roof.png", content_type="image/png"):
    return client.post(
        f"/api/v1/installation-jobs/{job_id}/photos",
        files={"file": (name, content, content_type)},
    )


def _complete(client, job_id, **overrides):
    body = {
        "system_kw": "1.08",
        "power_test_passed": True,
        "signer_name": "Ravi Kumar",
        "signature_png_base64": SIGNATURE,
        **overrides,
    }
    return client.post(f"/api/v1/installation-jobs/{job_id}/complete", json=body)


# ---------------------------------------------------------------- Schedule

def test_double_booking_other_date_ok_and_non_technician_rejected(db, api, office, manager):
    tech = _tech(db)
    first, second = _new_job(db, api, office), _new_job(db, api, office)
    assert _schedule(manager, first, [tech]).status_code == 200

    clash = _schedule(manager, second, [tech])
    _error(clash, 409, "TECHNICIAN_DOUBLE_BOOKED")
    assert tech.full_name in clash.json()["error"]["message"]

    tomorrow = _schedule(manager, second, [tech], TODAY + timedelta(days=1))
    assert tomorrow.status_code == 200, tomorrow.text
    assert tomorrow.json()["scheduled_date"] == (TODAY + timedelta(days=1)).isoformat()

    third = _new_job(db, api, office)
    office_user = _user(db, UserRole.OFFICE)
    _error(_schedule(manager, third, [_tech(db), office_user]), 422, "validation_error")
    _error(_schedule(manager, third, [tech], TODAY - timedelta(days=1)), 422, "validation_error")
    assert api(office_user).post(
        f"/api/v1/installation-jobs/{third}/schedule",
        json={"scheduled_date": TODAY.isoformat(), "technician_ids": [tech.id]},
    ).status_code == 403


# ---------------------------------------------------------------- Start

def test_start_needs_delivery_and_crew_membership(db, api, office, manager, delivered):
    tech = _tech(db)
    undelivered = _new_job(db, api, office)
    assert _schedule(manager, undelivered, [tech]).status_code == 200
    _error(
        api(tech).post(f"/api/v1/installation-jobs/{undelivered}/start"),
        409,
        "MATERIAL_NOT_DELIVERED",
    )

    crew = _tech(db)
    assert _schedule(manager, delivered["job_id"], [crew]).status_code == 200
    outsider = api(_tech(db))
    job_url = f"/api/v1/installation-jobs/{delivered['job_id']}"
    assert outsider.post(f"{job_url}/start").status_code == 403
    assert outsider.get(job_url).status_code == 403


# ---------------------------------------------------------------- Photos

def test_photo_type_from_bytes_and_size_limit(started):
    client, job_id = started["tech"], started["job_id"]
    _error(_photo(client, job_id, b"just text", "fake.jpg", "image/jpeg"), 422,
           "FILE_TYPE_NOT_ALLOWED")
    big = b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024)
    _error(_photo(client, job_id, big, "big.jpg", "image/jpeg"), 413, "FILE_TOO_LARGE")

    ok = _photo(client, job_id)
    assert ok.status_code == 201, ok.text
    assert ok.json()["kind"] == "photo"
    assert ok.json()["content_type"] == "image/png"

    file = client.get(f"/api/v1/evidence/{ok.json()['id']}/file")
    assert file.status_code == 200
    assert file.headers["content-type"] == "image/png"
    assert file.content == PNG
    sheet = client.get(f"/api/v1/installation-jobs/{job_id}").json()
    assert sheet["photo_ids"] == [ok.json()["id"]]
    assert any(line["serials"] for line in sheet["lines"])


# ---------------------------------------------------------------- Complete

def test_complete_needs_photo_power_test_and_real_signature(started):
    client, job_id = started["tech"], started["job_id"]
    _error(_complete(client, job_id), 409, "PHOTO_REQUIRED")
    assert _photo(client, job_id).status_code == 201

    _error(_complete(client, job_id, power_test_passed=False), 422, "validation_error")
    blank = base64.b64encode(PNG_MAGIC + b"\x00" * 100).decode()
    _error(_complete(client, job_id, signature_png_base64=blank), 422, "SIGNATURE_INVALID")
    _error(_complete(client, job_id, signature_png_base64="not base64!"), 422, "SIGNATURE_INVALID")
    _error(_complete(client, job_id, system_kw="0.1"), 422, "validation_error")


def test_hours_rounded_up_rate_snapshot_and_dashboard_labour(db, api, started):
    job_id = started["job_id"]
    first, second = started["crew"]
    job = db.get(InstallationJob, job_id)
    job.started_at = datetime.now(UTC) - timedelta(hours=2, minutes=10)
    first.hourly_rate = Decimal("999.00")  # rate change after booking must not matter
    db.commit()

    assert _photo(started["tech"], job_id).status_code == 201
    response = _complete(started["tech"], job_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["signer_name"] == "Ravi Kumar"
    assert {m["hours"] for m in body["crew"]} == {"2.25"}

    db.expire_all()
    rows = db.scalars(select(JobTechnician).where(JobTechnician.job_id == job_id)).all()
    assert sorted(r.hourly_rate for r in rows) == [Decimal("250.00"), Decimal("300.00")]
    assert db.get(Order, started["order_id"]).status == "installed"
    order_number = db.get(Order, started["order_id"]).order_number

    director = api(_user(db, UserRole.DIRECTOR))
    summary = director.get("/api/v1/dashboard/summary", params={"period": "month"}).json()
    row = next(r for r in summary["profit_per_job"] if r["order_number"] == order_number)
    assert row["labour_cost"] == "1237.50"  # 2.25 h x (250 + 300)


def test_work_hours_rounding():
    start = datetime(2026, 11, 14, 4, 30, tzinfo=UTC)  # 10:00 IST
    assert work_hours(start, start + timedelta(hours=2, minutes=10)) == Decimal("2.25")
    assert work_hours(start, start + timedelta(hours=2)) == Decimal("2.00")
    assert work_hours(start, start + timedelta(minutes=1)) == Decimal("0.25")
    assert work_hours(start, start) == Decimal("0.25")


# ---------------------------------------------------------------- My day

def test_me_today_shows_only_my_items(db, api, office, manager):
    mine, other = _tech(db), _tech(db)
    job_id = _new_job(db, api, office)
    assert _schedule(manager, job_id, [mine]).status_code == 200
    survey = _survey(db)
    survey.surveyor_id = mine.id
    survey.scheduled_at = datetime.now(UTC)
    db.commit()

    me = api(mine).get("/api/v1/me/today")
    assert me.status_code == 200, me.text
    assert [j["job_id"] for j in me.json()["installation_jobs"]] == [job_id]
    assert [s["id"] for s in me.json()["surveys"]] == [survey.id]

    theirs = api(other).get("/api/v1/me/today").json()
    assert theirs["installation_jobs"] == [] and theirs["surveys"] == []
    assert api(_user(db, UserRole.OFFICE)).get("/api/v1/me/today").status_code == 403

    schedule = manager.get(
        "/api/v1/schedule", params={"from": TODAY.isoformat(), "to": TODAY.isoformat()}
    )
    assert schedule.status_code == 200, schedule.text
    row = next(r for r in schedule.json()["items"] if r["job_id"] == job_id)
    assert [m["name"] for m in row["crew"]] == [mine.full_name]


@pytest.mark.parametrize("order_status", ["confirmed", "dispatched", "delivered"])
def test_planned_jobs_ignore_order_status(db, api, office, manager, order_status):
    from app.core.enums import InstallationJobStatus, OrderStatus

    job_id = _new_job(db, api, office)
    job = db.get(InstallationJob, job_id)
    db.get(Order, job.order_id).status = OrderStatus(order_status)
    db.commit()
    response = manager.get("/api/v1/installation-jobs?status=planned")
    assert response.status_code == 200
    assert job_id in [row["job_id"] for row in response.json()["items"]]
    assert api(office).get("/api/v1/installation-jobs?status=planned").status_code == 403
    job.status = InstallationJobStatus.SCHEDULED
    db.commit()
    assert job_id not in [row["job_id"] for row in manager.get(
        "/api/v1/installation-jobs?status=planned"
    ).json()["items"]]
