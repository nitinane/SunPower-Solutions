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
from app.models.catalog import Product
from app.models.dashboard import DashboardShareLink
from app.models.installations import InstallationJob, JobTechnician
from app.models.orders import Order, OrderItem
from app.models.quotes import Quote
from app.models.users import User
from app.services import dashboard as service

pytest_plugins = ["test_tickets"]


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


def _job(director, order_number, **params):
    body = director.get("/api/v1/dashboard/summary", params={"period": "month", **params}).json()
    return body, next(r for r in body["profit_per_job"] if r["order_number"] == order_number)


def test_free_warranty_replacement_lowers_profit_and_sorts_first(db, api, director, delivered):
    from test_replacement import _replace, _unit
    from test_tickets import _assign, _create_ticket, _resolve

    support = api(_user(db, UserRole.SUPPORT))
    order = db.get(Order, delivered["order_id"])
    _, before = _job(director, order.order_number)
    assert before["warranty_service_cost"] == "0.00"
    tech = _user(db, UserRole.TECHNICIAN)
    db.get(User, tech.id).hourly_rate = Decimal("100000.00")
    db.commit()
    ticket = _create_ticket(support, delivered)
    _assign(support, ticket["id"], tech)
    new = _unit(db, "INV-1K")
    assert _replace(api(tech), ticket["id"], new.serial_number).status_code == 200
    assert _resolve(api(tech), ticket["id"], hours="999.99").status_code == 200
    cost = db.get(Product, new.product_id).cost_price + Decimal("99999000.00")
    body, after = _job(director, order.order_number, sort="profit_asc")
    assert Decimal(after["warranty_service_cost"]) == cost
    assert Decimal(after["profit"]) == Decimal(before["profit"]) - cost < 0
    profits = [Decimal(r["profit"]) for r in body["profit_per_job"]]
    assert profits == sorted(profits)
    assert profits[0] == Decimal(after["profit"])


def test_stock_purchases_card_is_exact(db, director, warehouse):
    product = db.scalars(select(Product).where(Product.sku == "CON-MC4")).one()
    cost = product.cost_price
    before = Decimal(director.get("/api/v1/dashboard/summary").json()["cards"]["stock_purchases"])
    response = warehouse.post(
        "/api/v1/stock/receipts",
        json={
            "supplier_name": "Deccan Cables",
            "supplier_invoice_ref": "DC-77",
            "received_on": datetime.now(UTC).astimezone(service.BUSINESS_TZ).date().isoformat(),
            "lines": [{"product_id": product.id, "qty": "3", "unit_cost": "10.50"}],
        },
    )
    assert response.status_code == 201, response.text
    after = Decimal(director.get("/api/v1/dashboard/summary").json()["cards"]["stock_purchases"])
    assert after - before == Decimal("31.50")
    db.refresh(product)
    product.cost_price = cost
    db.commit()
