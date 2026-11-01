"""Phase 1 chain: fixture setup supplies staff/stock; every workflow action uses HTTP."""

import random
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_quotes import _user

from app.core.enums import UserRole
from app.main import create_app
from app.models.catalog import Product
from app.models.inventory import Inventory, SerializedUnit
from scripts.seed import seed_stock

pytest_plugins = ["test_quotes"]


def test_public_enquiry_to_closed_repair_and_dashboard(db, api, office):
    # Test setup only: users, catalog (db fixture), stock, and fresh serials.
    technician = _user(db, UserRole.TECHNICIAN)
    director = api(_user(db, UserRole.DIRECTOR))
    warehouse = api(_user(db, UserRole.WAREHOUSE))
    support = api(_user(db, UserRole.SUPPORT))
    tech = api(technician)
    seed_stock(db)
    stock_serials = {}
    for product in db.scalars(select(Product)):
        if product.tracks_serial:
            serial = f"E2E-{uuid4().hex.upper()}"
            db.add(SerializedUnit(product_id=product.id, serial_number=serial))
            stock_serials[product.sku] = serial
        elif product.category != "service":
            balance = db.scalars(
                select(Inventory).where(Inventory.product_id == product.id).with_for_update()
            ).one()
            balance.quantity_on_hand = Decimal("10000")
    db.commit()
    staff = api(office)
    public = TestClient(create_app())
    phone = f"98{random.randint(10_000_000, 99_999_999)}"
    response = public.post(
        "/api/v1/enquiries/public",
        json={
            "contact_name": "Ravi Kumar E2E",
            "phone": phone,
            "address_line": "12 Solar Street",
            "city": "Hyderabad",
            "state": "Telangana",
            "pincode": "500001",
            "customer_type": "home",
            "system_type": "on_grid",
            "requested_capacity_kw": "1.0",
            "subsidy_requested": False,
        },
    )
    assert response.status_code == 201, response.text
    reference = response.json()["reference"]
    # Resolve the public reference through the staff list API, not a database query.
    listing = staff.get("/api/v1/enquiries", params={"search": phone}).json()
    enquiry = next(row for row in listing["items"] if f"ENQ-{row['id']:06d}" == reference)
    enquiry_id = enquiry["id"]
    response = staff.post(
        f"/api/v1/enquiries/{enquiry_id}/qualification",
        json={
            "outcome": "qualified",
            "shadow_free_roof_area_sqft": "1000",
            "monthly_bill_amount": "5000",
            "grid_connection_suitable": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "qualified"
    response = staff.post(
        f"/api/v1/enquiries/{enquiry_id}/surveys",
        json={
            "surveyor_id": technician.id,
            "scheduled_at": "2026-11-02T10:00:00+05:30",
        },
    )
    assert response.status_code == 201, response.text
    survey_id = response.json()["id"]
    response = tech.post(
        f"/api/v1/surveys/{survey_id}/submit",
        json={
            "roof_direction": "south",
            "roof_tilt_deg": "20",
            "cable_distance_m": "15",
        },
    )
    assert response.status_code == 200, response.text
    assert director.post(f"/api/v1/surveys/{survey_id}/approve").status_code == 200
    packages = staff.get("/api/v1/packages", params={"package_type": "on_grid", "kw": "1"}).json()
    response = staff.post(
        "/api/v1/quotes", json={"survey_id": survey_id, "package_id": packages[0]["id"]}
    )
    assert response.status_code == 201, response.text
    quote_id = response.json()["id"]
    assert staff.post(f"/api/v1/quotes/{quote_id}/send").status_code == 200
    response = staff.post(f"/api/v1/quotes/{quote_id}/accept")
    assert response.status_code == 200, response.text
    order_id = response.json()["order_id"]
    response = staff.post(
        f"/api/v1/orders/{order_id}/payments", json={"amount": "1000.00", "method": "cash"}
    )
    assert response.status_code == 201, response.text
    order = response.json()["order"]
    assert order["pick_list"] and order["installation_job"]
    dispatch_id = order["pick_list"]["id"]
    detail = warehouse.get(f"/api/v1/dispatches/{dispatch_id}").json()
    inverter_serial = stock_serials["INV-1K"]
    for line in detail["lines"]:
        if line["requires_serial"]:
            response = warehouse.post(
                f"/api/v1/dispatches/{dispatch_id}/scan",
                json={"serial": stock_serials[line["sku"]]},
            )
            assert response.status_code == 200, response.text
    assert warehouse.post(f"/api/v1/dispatches/{dispatch_id}/send").status_code == 200
    response = warehouse.post(
        f"/api/v1/dispatches/{dispatch_id}/deliver", json={"receiver_name": "Ravi Kumar"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["warranties_created"] == 12
    results = support.get("/api/v1/support/search", params={"q": inverter_serial}).json()
    customer = next(row for row in results if row["customer"]["id"] == order["customer"]["id"])
    unit = next(unit for unit in customer["units"] if unit["serial"] == inverter_serial)
    assert unit["warranty_status"] == "active"
    response = support.post(
        "/api/v1/tickets",
        json={
            "customer_id": customer["customer"]["id"],
            "serialized_unit_id": unit["serialized_unit_id"],
            "fault_code": "NO_OUTPUT",
            "issue_description": "Output failed",
            "priority": "high",
        },
    )
    assert response.status_code == 201, response.text
    ticket_id = response.json()["id"]
    assert (
        support.post(
            f"/api/v1/tickets/{ticket_id}/assign",
            json={
                "technician_id": technician.id,
                "visit_date": "2026-11-03",
            },
        ).status_code
        == 200
    )
    response = tech.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        json={
            "work_notes": "Reset and tested",
            "labour_hours": "1.50",
            "parts": [],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved" and response.json()["total"] == "0.00"
    response = support.post(
        f"/api/v1/tickets/{ticket_id}/confirm",
        json={
            "confirmed": True,
            "customer_name": "Ravi Kumar",
            "note": "Working again",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "closed"
    response = director.get("/api/v1/dashboard/summary?period=month")
    assert response.status_code == 200, response.text
    assert any(
        row["order_number"] == order["order_number"] for row in response.json()["profit_per_job"]
    )
