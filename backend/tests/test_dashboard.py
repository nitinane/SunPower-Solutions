"""SQL profit aggregates, IST periods, and hashed dashboard shares."""

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_quotes import _user

from app.core.enums import UserRole
from app.main import create_app
from app.models.dashboard import DashboardShareLink
from app.models.installations import InstallationJob, JobTechnician
from app.models.orders import Order, OrderItem
from app.models.quotes import Quote
from app.services import dashboard as service

pytest_plugins = ["test_dispatch"]


@pytest.fixture
def director(db, api):
    return api(_user(db, UserRole.DIRECTOR))


def test_profit_uses_snapshots_and_labour_sql(db, director, pick):
    order = db.get(Order, pick["order_id"])
    quote = db.get(Quote, order.quote_id)
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    material = sum((item.quantity * item.unit_cost for item in items), Decimal("0"))
    tech = _user(db, UserRole.TECHNICIAN)
    job = db.scalars(select(InstallationJob).where(InstallationJob.order_id == order.id)).one()
    db.add(
        JobTechnician(
            job_id=job.id,
            technician_id=tech.id,
            hours_worked=Decimal("2.25"),
            hourly_rate=Decimal("250.00"),
        )
    )
    db.commit()
    response = director.get("/api/v1/dashboard/summary", params={"period": "month"})
    assert response.status_code == 200, response.text
    body = response.json()
    row = next(row for row in body["profit_per_job"] if row["order_number"] == order.order_number)
    assert Decimal(row["revenue"]) == quote.subtotal
    assert Decimal(row["material_cost"]) == material
    assert row["labour_cost"] == "562.50"
    assert Decimal(row["profit"]) == quote.subtotal - material - Decimal("562.50")
    assert body["cards"]["unfinished_jobs"] >= 1
    assert any(row["order_number"] == order.order_number for row in body["unfinished_jobs"])


def test_period_boundaries_are_ist(db, director, pick, monkeypatch):
    fixed = datetime(2026, 11, 4, 7, 0, tzinfo=UTC)
    monkeypatch.setattr(service, "_now", lambda: fixed)
    order = db.get(Order, pick["order_id"])
    # Nov 2 00:15 IST: inside the current week, though UTC is still Nov 1.
    order.confirmed_at = datetime(2026, 11, 1, 18, 45, tzinfo=UTC)
    db.commit()
    response = director.get("/api/v1/dashboard/summary?period=week")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["from_at"] == "2026-11-01T18:30:00Z"
    assert any(row["order_number"] == order.order_number for row in body["profit_per_job"])
    order.confirmed_at = datetime(2026, 10, 31, 18, 29, tzinfo=UTC)
    db.commit()
    body = director.get("/api/v1/dashboard/summary?period=week").json()
    assert all(row["order_number"] != order.order_number for row in body["profit_per_job"])
    body = director.get("/api/v1/dashboard/summary?period=month").json()
    assert body["from_at"] == "2026-10-31T18:30:00Z"
    body = director.get("/api/v1/dashboard/summary?period=today").json()
    assert body["from_at"] == "2026-11-03T18:30:00Z"


def test_share_public_expired_revoked_and_unknown_are_identical(db, director):
    response = director.post("/api/v1/dashboard/share", json={"period": "month"})
    assert response.status_code == 201, response.text
    share = response.json()
    token = share["url"].split("/")[-1]
    row = db.get(DashboardShareLink, share["id"])
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in row.token_hash
    public = TestClient(create_app())
    path = f"/api/v1/public/dashboard/{token}"
    body = public.get(path)
    assert body.status_code == 200, body.text
    assert (
        body.json()["cards"]
        == director.get("/api/v1/dashboard/summary?period=month").json()["cards"]
    )
    assert director.delete(f"/api/v1/dashboard/share/{row.id}").status_code == 204
    revoked = public.get(path)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    row.revoked_at = None
    db.commit()
    expired = public.get(path)
    unknown = public.get("/api/v1/public/dashboard/unknown-token")
    assert revoked.status_code == expired.status_code == unknown.status_code == 404
    assert revoked.json() == expired.json() == unknown.json()


def test_dashboard_director_only_and_expiry_limit(api, office):
    client = api(office)
    assert client.get("/api/v1/dashboard/summary").status_code == 403
    assert client.post("/api/v1/dashboard/share", json={"period": "month"}).status_code == 403
    assert client.delete("/api/v1/dashboard/share/1").status_code == 403


def test_dashboard_share_validation(director):
    for body in (
        {"period": "year"},
        {"period": "month", "expires_in_hours": 169},
        {"period": "month", "expires_in_hours": 0},
    ):
        assert director.post("/api/v1/dashboard/share", json=body).status_code == 422
