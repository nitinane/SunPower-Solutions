"""Problem-statement gaps: retained enquiries and usable crew dropdowns."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from test_enquiry_schemas import public_payload
from test_quotes import _user

from app.core.enums import UserRole
from app.main import create_app

pytest_plugins = ["test_quotes"]


@pytest.mark.parametrize("source", ["website", "phone", "whatsapp"])
@pytest.mark.parametrize("customer_type", ["home", "factory"])
def test_enquiry_sources_retained_with_history(db, api, office, source, customer_type):
    staff = api(office)
    body = public_payload()
    # Unique, valid Indian mobile number per case without shared test data.
    body["phone"] = "9" + str(int(uuid4().hex[:10], 16) % 1_000_000_000).zfill(9)
    body["customer_type"] = customer_type
    key = uuid4().hex
    if source == "website":
        client, path = TestClient(create_app()), "/api/v1/enquiries/public"
    else:
        body.pop("website_url")
        body["source"] = source
        client, path = staff, "/api/v1/enquiries"
    created = client.post(path, json=body, headers={"Idempotency-Key": key})
    assert created.status_code == 201, created.text
    repeated = client.post(path, json=body, headers={"Idempotency-Key": key})
    assert repeated.status_code in (200, 201), repeated.text
    rows = staff.get("/api/v1/enquiries", params={"search": body["phone"]}).json()["items"]
    assert len(rows) == 1
    row = rows[0]
    for field in ("customer_type", "subsidy_requested"):
        assert row[field] == body[field]
    assert Decimal(row["requested_capacity_kw"]) == Decimal(body["requested_capacity_kw"])
    assert row["source"] == source
    closed = staff.post(
        f"/api/v1/enquiries/{row['id']}/close", json={"reason": "Customer deferred"}
    )
    assert closed.status_code == 200, closed.text
    assert staff.get(f"/api/v1/enquiries/{row['id']}").json()["status"] == "closed"
    history = staff.get(f"/api/v1/enquiries/{row['id']}/history").json()
    assert {event["action"] for event in history} >= {"enquiry.created", "enquiry.closed"}


def test_manager_can_load_crew_dropdown_without_private_costs(db, api):
    tech = _user(db, UserRole.TECHNICIAN)
    manager = api(_user(db, UserRole.MANAGER))
    response = manager.get("/api/v1/users", params={"role": "technician"})
    assert response.status_code == 200, response.text
    assert any(row["id"] == tech.id for row in response.json())
    assert all(row["role"] == "technician" for row in response.json())
    assert all(set(row) == {"id", "full_name", "role", "phone"} for row in response.json())
    assert api(tech).get("/api/v1/users").status_code == 403
