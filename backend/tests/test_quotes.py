"""Quotes from package templates + catalog seed (real Postgres)."""

import random
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import SESSION_COOKIE
from app.core.enums import EnquiryStatus, PackageType, SurveyStatus, UserRole
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import create_app
from app.models.auth import AuditLog
from app.models.catalog import Product
from app.models.customers import Customer, Site
from app.models.enquiries import Enquiry
from app.models.orders import Order, OrderItem
from app.models.surveys import SiteSurvey
from app.models.users import User
from app.repositories import catalog as catalog_repo
from scripts.seed import seed_catalog


@pytest.fixture
def db() -> Iterator[Session]:
    session = SessionLocal()
    seed_catalog(session)
    session.commit()
    try:
        yield session
    finally:
        session.close()


def _user(db: Session, role: UserRole) -> User:
    user = User(
        full_name=f"Test {role}",
        email=f"t-{uuid.uuid4().hex[:12]}@test.sunpower.in",
        role=role,
        password_hash="x",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def api() -> Callable[[User], TestClient]:
    app = create_app()

    def as_user(user: User) -> TestClient:
        token = create_access_token(str(user.id))
        return TestClient(app, headers={"Cookie": f"{SESSION_COOKIE}={token}"})

    return as_user


@pytest.fixture
def office(db: Session) -> User:
    return _user(db, UserRole.OFFICE)


def _survey(db: Session, status: SurveyStatus = SurveyStatus.APPROVED) -> SiteSurvey:
    phone = f"+9198{random.randint(10_000_000, 99_999_999)}"
    customer = Customer(full_name="Quote Customer", phone_e164=phone)
    db.add(customer)
    db.flush()
    site = Site(
        customer_id=customer.id, address_line1="12 Sun Street", city="Pune",
        state="Maharashtra", pincode="411001",
    )
    db.add(site)
    db.flush()
    enquiry = Enquiry(
        customer_id=customer.id, site_id=site.id, contact_name="Quote Customer",
        phone_raw=phone, phone_e164=phone, address_line="12 Sun Street", city="Pune",
        state="Maharashtra", pincode="411001", requested_capacity_kw=Decimal("5"),
        system_type="on_grid", customer_type="home", source="phone",
        status=EnquiryStatus.QUALIFIED,
    )
    db.add(enquiry)
    db.flush()
    surveyor = _user(db, UserRole.SURVEYOR)
    reviewer = _user(db, UserRole.DIRECTOR)
    reviewed = status in (SurveyStatus.APPROVED, SurveyStatus.REJECTED)
    survey = SiteSurvey(
        enquiry_id=enquiry.id, site_id=site.id, surveyor_id=surveyor.id, status=status,
        reviewed_by=reviewer.id if reviewed else None,
        reviewed_at=datetime.now(UTC) if reviewed else None,
    )
    db.add(survey)
    db.commit()
    return survey


def _package_id(db: Session, package_type: PackageType, kw: int) -> int:
    return catalog_repo.find_package(db, package_type, Decimal(kw)).id


def _create(client: TestClient, survey_id: int, package_id: int, install: bool = False) -> dict:
    response = client.post(
        "/api/v1/quotes",
        json={"survey_id": survey_id, "package_id": package_id, "include_installation": install},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _qty(quote: dict) -> dict[str, str]:
    return {line["sku"]: line["qty"] for line in quote["lines"]}


def test_survey_not_approved_is_409(db, api, office):
    survey = _survey(db, SurveyStatus.SUBMITTED)
    response = api(office).post(
        "/api/v1/quotes",
        json={"survey_id": survey.id, "package_id": _package_id(db, PackageType.ON_GRID, 5)},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SURVEY_NOT_APPROVED"


def test_5kw_on_grid_parts_list(db, api, office):
    quote = _create(api(office), _survey(db).id, _package_id(db, PackageType.ON_GRID, 5))
    assert quote["status"] == "draft"
    assert quote["quote_number"] == f"QT-{quote['id']:06d}"
    assert _qty(quote) == {
        "PNL-540": "10.000", "CON-MC4": "10.000", "WIRE-DC4": "20.000", "INV-5K": "1.000",
        "CC-MPPT-40": "1.000", "STD-GI": "10.000", "WIRE-AC6": "15.000", "BOX-ACDB": "1.000",
        "BOX-DCDB": "1.000", "SW-MCB": "2.000", "EARTH-KIT": "1.000", "EARTH-LA": "1.000",
    }


def test_off_grid_has_batteries_and_panel_set_has_no_inverter(db, api, office):
    client = api(office)
    off_grid = _create(client, _survey(db).id, _package_id(db, PackageType.OFF_GRID, 3))
    assert _qty(off_grid)["BAT-150AH"] == "3.000"
    assert _qty(off_grid)["PNL-540"] == "6.000"

    panel_set = _create(client, _survey(db).id, _package_id(db, PackageType.PANEL_SET, 3))
    assert set(_qty(panel_set)) == {"PNL-540", "CON-MC4", "WIRE-DC4"}


def test_include_installation_adds_service_at_18_percent(db, api, office):
    quote = _create(api(office), _survey(db).id, _package_id(db, PackageType.ON_GRID, 4), True)
    line = next(line for line in quote["lines"] if line["sku"] == "SVC-INSTALL")
    assert line["qty"] == "4.000"
    assert line["gst_percent"] == "18.00"
    assert line["line_total"] == "18000.00"
    assert line["gst_amount"] == "3240.00"


def test_totals_are_sums_of_quantized_lines(db, api, office):
    # 1 kW panel set: 2 panels, 2 MC4 pairs, 20 m DC wire (all 12% GST)
    quote = _create(api(office), _survey(db).id, _package_id(db, PackageType.PANEL_SET, 1))
    assert [(x["sku"], x["line_total"], x["gst_amount"]) for x in quote["lines"]] == [
        ("PNL-540", "28000.00", "3360.00"),
        ("CON-MC4", "240.00", "28.80"),
        ("WIRE-DC4", "1400.00", "168.00"),
    ]
    assert (quote["subtotal"], quote["gst"], quote["total"]) == (
        "29640.00", "3556.80", "33196.80"
    )


def test_price_change_after_quoting_leaves_quote_and_order_unchanged(db, api, office):
    client = api(office)
    quote = _create(client, _survey(db).id, _package_id(db, PackageType.PANEL_SET, 2))
    panel = db.scalars(select(Product).where(Product.sku == "PNL-540")).one()
    original = panel.sale_price
    try:
        panel.sale_price = Decimal("99999.00")
        db.commit()
        again = client.get(f"/api/v1/quotes/{quote['id']}").json()
        assert again["lines"] == quote["lines"]
        assert again["total"] == quote["total"]

        assert client.post(f"/api/v1/quotes/{quote['id']}/send").status_code == 200
        accepted = client.post(f"/api/v1/quotes/{quote['id']}/accept").json()
        item = db.scalars(
            select(OrderItem).where(
                OrderItem.order_id == accepted["order_id"], OrderItem.sku_snapshot == "PNL-540"
            )
        ).one()
        assert item.unit_price == Decimal("14000.00")
    finally:
        panel.sale_price = original
        db.commit()


def test_accept_creates_one_order_and_second_accept_is_409(db, api, office):
    client = api(office)
    quote = _create(client, _survey(db).id, _package_id(db, PackageType.ON_GRID, 2), True)
    assert client.post(f"/api/v1/quotes/{quote['id']}/send").json()["status"] == "sent"

    response = client.post(f"/api/v1/quotes/{quote['id']}/accept")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["quote"]["status"] == "accepted"

    orders = db.scalars(select(Order).where(Order.quote_id == quote["id"])).all()
    assert len(orders) == 1
    order = orders[0]
    assert order.id == body["order_id"]
    assert order.status == "pending_payment"
    assert order.order_number == f"ORD-{order.id:06d}"
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    assert sorted((i.sku_snapshot, str(i.quantity), str(i.unit_price), str(i.gst_rate))
                  for i in items) == sorted(
        (x["sku"], x["qty"], x["unit_price"], x["gst_percent"]) for x in quote["lines"]
    )

    again = client.post(f"/api/v1/quotes/{quote['id']}/accept")
    assert again.status_code == 409
    assert len(db.scalars(select(Order).where(Order.quote_id == quote["id"])).all()) == 1


def test_accept_cancels_other_open_quotes_of_same_enquiry(db, api, office):
    client = api(office)
    survey = _survey(db)
    first = _create(client, survey.id, _package_id(db, PackageType.ON_GRID, 3))
    second = _create(client, survey.id, _package_id(db, PackageType.OFF_GRID, 3))
    client.post(f"/api/v1/quotes/{first['id']}/send")
    assert client.post(f"/api/v1/quotes/{first['id']}/accept").status_code == 200

    assert client.get(f"/api/v1/quotes/{second['id']}").json()["status"] == "cancelled"
    audit = db.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "quote",
            AuditLog.entity_id == second["id"],
            AuditLog.action == "quote.cancelled",
        )
    ).one()
    assert audit.new_data["reason"] == "another quote was accepted"


def test_reject_needs_reason_and_technician_is_forbidden(db, api, office):
    client = api(office)
    quote = _create(client, _survey(db).id, _package_id(db, PackageType.PANEL_SET, 1))
    client.post(f"/api/v1/quotes/{quote['id']}/send")

    assert client.post(f"/api/v1/quotes/{quote['id']}/reject", json={}).status_code == 422
    tech = api(_user(db, UserRole.TECHNICIAN))
    assert tech.post(
        f"/api/v1/quotes/{quote['id']}/reject", json={"reason": "too costly"}
    ).status_code == 403
    assert tech.get("/api/v1/packages").status_code == 403

    response = client.post(f"/api/v1/quotes/{quote['id']}/reject", json={"reason": "too costly"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_packages_endpoint_filters(db, api, office):
    response = api(office).get("/api/v1/packages", params={"package_type": "on_grid", "kw": 5})
    assert response.status_code == 200
    packages = response.json()
    assert [p["name"] for p in packages] == ["5 kW On-grid system"]
    assert len(packages[0]["components"]) == 12


def test_seed_catalog_twice_is_idempotent(db):
    assert seed_catalog(db) == (0, 0)
    db.commit()
    assert catalog_repo.count_products(db) == 18
    assert catalog_repo.count_packages(db) == 15
