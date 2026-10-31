"""Order payment workflow against real PostgreSQL."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_quotes import _create, _package_id, _survey, _user

from app.core.enums import EnquiryStatus, PackageType, UserRole
from app.models.auth import AuditLog
from app.models.dispatch import Dispatch
from app.models.enquiries import Enquiry
from app.models.installations import InstallationJob
from app.models.orders import Order
from app.models.payments import Payment
from app.models.quotes import Quote

pytest_plugins = ["test_quotes"]


def _order(db, client):
    survey = _survey(db)
    quote = _create(client, survey.id, _package_id(db, PackageType.PANEL_SET, 1))
    # Exact money fixture; production totals are frozen by quote creation.
    row = db.get(Quote, quote["id"])
    row.subtotal = Decimal("150000.00")
    row.tax_total = Decimal("0.00")
    row.total = Decimal("150000.00")
    db.commit()
    assert client.post(f"/api/v1/quotes/{row.id}/send").status_code == 200
    accepted = client.post(f"/api/v1/quotes/{row.id}/accept")
    assert accepted.status_code == 200, accepted.text
    return accepted.json()["order_id"], survey.enquiry_id


def _pay(client, order_id, amount="50000.00", **kwargs):
    body = {"amount": amount, "method": "cash"}
    body.update(kwargs.pop("body", {}))
    return client.post(f"/api/v1/orders/{order_id}/payments", json=body, **kwargs)


def _count(db, model, order_id):
    return db.scalar(select(func.count()).select_from(model).where(model.order_id == order_id))


def test_qualification_requires_all_call_checks(db, api, office):
    survey = _survey(db)
    enquiry = db.get(Enquiry, survey.enquiry_id)
    enquiry.status = EnquiryStatus.NEW
    db.commit()
    response = api(office).post(
        f"/api/v1/enquiries/{enquiry.id}/qualification", json={"outcome": "qualified"}
    )
    assert response.status_code == 422, response.text
    assert set(response.json()["error"]["fields"]) == {
        "shadow_free_roof_area_sqft", "monthly_bill_amount", "grid_connection_suitable",
    }
    db.refresh(enquiry)
    assert enquiry.status == EnquiryStatus.NEW


def test_accept_converts_enquiry_and_audits(db, api, office):
    order_id, enquiry_id = _order(db, api(office))
    db.expire_all()
    assert db.get(Enquiry, enquiry_id).status == EnquiryStatus.CONVERTED
    audit = db.scalars(select(AuditLog).where(
        AuditLog.entity_type == "enquiry", AuditLog.entity_id == enquiry_id,
        AuditLog.action == "enquiry.converted",
    )).one()
    assert audit.new_data == {"status": "converted", "order_id": order_id}


def test_advance_then_balance_starts_work_once(db, api, office):
    client = api(office)
    order_id, _ = _order(db, client)
    response = _pay(client, order_id)
    assert response.status_code == 201, response.text
    first = response.json()
    assert first["payment"]["kind"] == "advance"
    assert first["order"]["status"] == "confirmed"
    assert first["order"]["confirmed_at"] is not None
    assert first["order"]["amount_paid"] == "50000.00"
    assert first["order"]["balance_due"] == "100000.00"
    assert first["order"]["pick_list"]["status"] == "draft"
    assert first["order"]["installation_job"]["status"] == "planned"
    assert first["order"]["installation_job"]["scheduled_date"] is None
    assert _count(db, Dispatch, order_id) == _count(db, InstallationJob, order_id) == 1
    response = _pay(client, order_id, "100000.00")
    assert response.status_code == 201, response.text
    second = response.json()
    assert second["payment"]["kind"] == "balance"
    assert second["order"]["balance_due"] == "0.00"
    assert second["order"]["pick_list"] == first["order"]["pick_list"]
    assert second["order"]["installation_job"] == first["order"]["installation_job"]
    assert _count(db, Dispatch, order_id) == _count(db, InstallationJob, order_id) == 1
    assert _count(db, Payment, order_id) == 2
    actions = list(db.scalars(select(AuditLog.action).where(
        (AuditLog.entity_type == "order") & (AuditLog.entity_id == order_id)
    )))
    assert actions.count("order.confirmed") == 1
    for action, entity, entity_id in [
        ("pick_list.created", "dispatch", first["order"]["pick_list"]["id"]),
        ("installation_job.created", "installation_job", first["order"]["installation_job"]["id"]),
    ]:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == action, AuditLog.entity_type == entity,
            AuditLog.entity_id == entity_id,
        )) == 1
    for payment in second["order"]["payments"]:
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "payment.recorded", AuditLog.entity_type == "payment",
            AuditLog.entity_id == payment["id"],
        )) == 1


def test_first_full_payment(db, api, office):
    client = api(office)
    order_id, _ = _order(db, client)
    response = _pay(client, order_id, "150000.00")
    assert response.status_code == 201, response.text
    assert response.json()["payment"]["kind"] == "full"
    assert response.json()["order"]["balance_due"] == "0.00"


def test_overpayment_changes_nothing(db, api, office):
    client = api(office)
    order_id, _ = _order(db, client)
    response = _pay(client, order_id, "150000.01")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "OVERPAYMENT"
    assert "150000.00" in response.json()["error"]["message"]
    assert "₹" in response.json()["error"]["message"]
    for model in (Payment, Dispatch, InstallationJob):
        assert _count(db, model, order_id) == 0
    db.expire_all()
    assert db.get(Order, order_id).status == "pending_payment"


def test_duplicate_reference_rolls_back(db, api, office):
    client = api(office)
    first, _ = _order(db, client)
    second, _ = _order(db, client)
    body = {"method": "upi", "reference": uuid4().hex}
    assert _pay(client, first, body=body).status_code == 201
    response = _pay(client, second, body=body)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "DUPLICATE_PAYMENT_REFERENCE"
    for model in (Payment, Dispatch, InstallationJob):
        assert _count(db, model, second) == 0
    db.expire_all()
    assert db.get(Order, second).status == "pending_payment"


def test_idempotent_retry_returns_existing_payment(db, api, office):
    client = api(office)
    order_id, _ = _order(db, client)
    headers = {"Idempotency-Key": uuid4().hex}
    first = _pay(client, order_id, "150000.00", headers=headers)
    second = _pay(client, order_id, "150000.00", headers=headers)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert second.json() == first.json()
    for model in (Payment, Dispatch, InstallationJob):
        assert _count(db, model, order_id) == 1


def test_idempotency_key_cannot_mix_orders(db, api, office):
    client = api(office)
    first, _ = _order(db, client)
    second, _ = _order(db, client)
    headers = {"Idempotency-Key": uuid4().hex}
    assert _pay(client, first, headers=headers).status_code == 201
    response = _pay(client, second, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert _count(db, Payment, second) == 0


def test_cancelled_order_not_payable(db, api, office):
    client = api(office)
    order_id, _ = _order(db, client)
    db.get(Order, order_id).status = "cancelled"
    db.commit()
    response = _pay(client, order_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOT_PAYABLE"
    assert _count(db, Payment, order_id) == 0


@pytest.mark.parametrize("role", [UserRole.TECHNICIAN, UserRole.MANAGER, UserRole.WAREHOUSE])
def test_only_cashiers_can_record_payments(db, api, office, role):
    order_id, _ = _order(db, api(office))
    response = _pay(api(_user(db, role)), order_id)
    assert response.status_code == 403
    assert _count(db, Payment, order_id) == 0


@pytest.mark.parametrize("body", [
    {"amount": "0"}, {"amount": "-1"}, {"amount": "0.001"},
    {"method": "upi"}, {"method": "upi", "reference": "   "},
    {"kind": "full"},
])
def test_invalid_payment_input(db, api, office, body):
    client = api(office)
    order_id, _ = _order(db, client)
    response = _pay(client, order_id, body=body)
    assert response.status_code == 422, response.text
    assert _count(db, Payment, order_id) == 0


def test_order_lists_filters_pagination_and_detail(db, api, office):
    client = api(office)
    first, _ = _order(db, client)
    second, _ = _order(db, client)
    assert _pay(client, second).status_code == 201
    manager = api(_user(db, UserRole.MANAGER))
    number = db.get(Order, second).order_number
    listing = manager.get("/api/v1/orders", params={"search": number, "status": "confirmed"})
    assert listing.status_code == 200, listing.text
    assert [row["id"] for row in listing.json()["items"]] == [second]
    detail = manager.get(f"/api/v1/orders/{second}")
    assert detail.status_code == 200, detail.text
    order = detail.json()
    assert order["customer"]["name"] == "Quote Customer"
    assert order["site"]["address_line1"] == "12 Sun Street"
    assert order["items"][0]["sku"] == "PNL-540"
    assert order["items"][0]["line_total"] == "28000.00"
    assert order["items"][0]["requires_serial"] is False
    for search in (order["customer"]["phone"], order["customer"]["name"]):
        response = manager.get("/api/v1/orders", params={"search": search, "page_size": 100})
        assert response.status_code == 200
        assert second in [row["id"] for row in response.json()["items"]]
    listing = manager.get("/api/v1/orders", params={"page_size": 1}).json()
    assert listing["items"][0]["id"] == second
    assert listing["page_size"] == 1
    warehouse = api(_user(db, UserRole.WAREHOUSE))
    assert warehouse.get(f"/api/v1/orders/{first}").status_code == 200
    assert warehouse.get("/api/v1/orders").status_code == 403
    technician = api(_user(db, UserRole.TECHNICIAN))
    assert technician.get(f"/api/v1/orders/{first}").status_code == 403
    assert technician.get("/api/v1/orders").status_code == 403
