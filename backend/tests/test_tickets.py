"""Repair billing, ownership, and customer confirmation against PostgreSQL."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from test_dispatch import _scan_all, _send
from test_quotes import _user

from app.core.enums import UserRole
from app.models.catalog import Product
from app.models.customers import Customer
from app.models.inventory import Inventory, StockMovement
from app.models.orders import Order, OrderItem
from app.models.service_tickets import SupportTicket, TicketCharge
from app.models.warranties import Warranty
from app.repositories import tickets as ticket_repo

pytest_plugins = ["test_dispatch"]


@pytest.fixture
def support(db, api):
    return api(_user(db, UserRole.SUPPORT))


@pytest.fixture
def delivered(db, warehouse, pick):
    _scan_all(warehouse, pick)
    assert _send(warehouse, pick).status_code == 200
    response = warehouse.post(
        f"/api/v1/dispatches/{pick['id']}/deliver", json={"receiver_name": "Ravi Kumar"}
    )
    assert response.status_code == 200, response.text
    order = db.get(Order, pick["order_id"])
    return {**pick, "customer_id": order.customer_id, "unit_id": pick["serials"]["INV-1K"].id}


def _create_ticket(client, delivered):
    response = client.post(
        "/api/v1/tickets",
        json={
            "customer_id": delivered["customer_id"],
            "serialized_unit_id": delivered["unit_id"],
            "fault_code": "NO_POWER",
            "issue_description": "Inverter has no output",
            "priority": "high",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assign(client, ticket_id, technician):
    response = client.post(
        f"/api/v1/tickets/{ticket_id}/assign",
        json={
            "technician_id": technician.id,
            "visit_date": "2026-11-02",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _resolve(client, ticket_id, parts=None, hours="2.25"):
    return client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        json={
            "work_notes": "Replaced connector and tested output",
            "labour_hours": hours,
            "parts": parts or [],
        },
    )


def _expire(db, delivered):
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    warranty = db.scalars(
        select(Warranty).where(Warranty.serialized_unit_id == delivered["unit_id"])
    ).one()
    warranty.start_date = today - timedelta(days=900)
    warranty.end_date = today - timedelta(days=1)
    db.commit()


def test_support_search_phone_serial_and_name(db, support, delivered):
    customer = db.get(Customer, delivered["customer_id"])
    # Unique name isolates prefix lookup in a shared development database.
    customer.full_name = f"Ravi {uuid4().hex}"
    original_phone = customer.phone_e164
    customer.phone_e164 = "+919876543210"
    db.commit()
    ticket = _create_ticket(support, delivered)
    for query in (
        "98765 43210",
        "+91-98765-43210",
        delivered["serials"]["INV-1K"].serial_number,
        customer.full_name,
    ):
        response = support.get("/api/v1/support/search", params={"q": query})
        assert response.status_code == 200, response.text
        results = response.json()
        assert len(results) <= 10
        result = next(row for row in results if row["customer"]["id"] == customer.id)
        assert result["sites"] and result["orders"]
        assert result["units"][0]["warranty_status"] == "active"
        assert result["open_tickets"][0]["id"] == ticket["id"]
    customer.phone_e164 = original_phone
    db.commit()


def test_under_warranty_free_but_parts_consumed(db, api, support, delivered):
    ticket = _create_ticket(support, delivered)
    assert ticket["coverage_label"] == "Under warranty – free"
    # Coverage is frozen when opened, even if the warranty expires before the visit.
    _expire(db, delivered)
    tech = _user(db, UserRole.TECHNICIAN)
    _assign(support, ticket["id"], tech)
    product = db.scalars(select(Product).where(Product.sku == "CON-MC4")).one()
    stock = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).one()
    before = stock.quantity_on_hand
    response = _resolve(api(tech), ticket["id"], [{"product_id": product.id, "qty": "2"}])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "resolved"
    assert body["total"] == body["gst"] == body["parts_subtotal"] == body["labour_amount"] == "0.00"
    assert body["labour_hours"] == "2.25"
    assert all(row["amount"] == row["customer_price"] == "0.00" for row in body["charges"])
    assert any(row["action"] == "ticket.resolved" for row in body["history"])
    db.refresh(stock)
    assert stock.quantity_on_hand == before - 2


def test_expired_warranty_billed_exactly(db, support, delivered):
    _expire(db, delivered)
    ticket = _create_ticket(support, delivered)
    assert ticket["coverage_label"] == "Out of warranty – billable"
    _assign(support, ticket["id"], _user(db, UserRole.TECHNICIAN))
    product = db.scalars(select(Product).where(Product.sku == "CON-MC4")).one()
    response = _resolve(support, ticket["id"], [{"product_id": product.id, "qty": "2"}])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parts_subtotal"] == "240.00"
    assert body["labour_amount"] == "1125.00"
    assert body["gst"] == "231.30"
    assert body["total"] == "1596.30"
    assert body["charges"][0]["customer_price"] == "120.00"
    movement = db.scalars(
        select(StockMovement).where(
            StockMovement.reference_type == "ticket", StockMovement.reference_id == ticket["id"]
        )
    ).one()
    assert movement.quantity_delta == Decimal("-2") and movement.reason == "service"


def test_confirmation_is_only_close_path_and_rejection_reopens(db, api, support, office, delivered):
    ticket = _create_ticket(support, delivered)
    path = f"/api/v1/tickets/{ticket['id']}"
    confirm = {"confirmed": True, "customer_name": "Ravi Kumar"}
    assert support.post(path + "/confirm", json=confirm).status_code == 409
    tech = _user(db, UserRole.TECHNICIAN)
    _assign(support, ticket["id"], tech)
    response = _resolve(api(tech), ticket["id"])
    assert response.json()["status"] == "resolved"
    assert api(tech).post(path + "/confirm", json=confirm).status_code == 403
    assert _resolve(api(tech), ticket["id"]).status_code == 409
    rejected = support.post(
        path + "/confirm",
        json={
            "confirmed": False,
            "customer_name": "Ravi Kumar",
            "note": "Still intermittent",
        },
    )
    assert rejected.json()["status"] == "open"
    assert rejected.json()["customer_confirmed_at"] is None
    assert rejected.json()["history"][-1]["new_data"]["note"] == "Still intermittent"
    _assign(support, ticket["id"], tech)
    assert _resolve(api(tech), ticket["id"], hours="0").status_code == 200
    closed = api(office).post(path + "/confirm", json=confirm)
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert closed.json()["confirmed_by_name"] == "Ravi Kumar"
    assert closed.json()["customer_confirmed_at"] is not None


def test_technician_access_is_own_only(db, api, support, delivered):
    ticket = _create_ticket(support, delivered)
    assigned = _user(db, UserRole.TECHNICIAN)
    other = _user(db, UserRole.TECHNICIAN)
    _assign(support, ticket["id"], assigned)
    assert _resolve(api(other), ticket["id"]).status_code == 403
    assert api(other).get(f"/api/v1/tickets/{ticket['id']}").status_code == 403
    assert api(other).get("/api/v1/tickets").json()["items"] == []
    assert api(assigned).get("/api/v1/tickets").json()["items"][0]["id"] == ticket["id"]
    assert api(assigned).get("/api/v1/support/search", params={"q": "Ravi"}).status_code == 403


def test_parts_shortage_and_serial_replacement_rejected_without_writes(db, support, delivered):
    ticket = _create_ticket(support, delivered)
    _assign(support, ticket["id"], _user(db, UserRole.TECHNICIAN))
    product = db.scalars(select(Product).where(Product.sku == "CON-MC4")).one()
    stock = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).one()
    before = stock.quantity_on_hand
    response = _resolve(support, ticket["id"], [{"product_id": product.id, "qty": "999999"}])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    serial_product = delivered["serials"]["INV-1K"].product_id
    assert (
        _resolve(support, ticket["id"], [{"product_id": serial_product, "qty": "1"}]).status_code
        == 422
    )
    db.expire_all()
    assert stock.quantity_on_hand == before
    assert db.get(SupportTicket, ticket["id"]).status == "assigned"
    assert (
        db.scalar(
            select(func.count())
            .select_from(TicketCharge)
            .where(TicketCharge.ticket_id == ticket["id"])
        )
        == 0
    )


def test_ticket_target_validation_and_bulk_warranty(db, support, delivered):
    item = db.scalars(
        select(OrderItem)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == delivered["order_id"], Product.sku == "PNL-540")
    ).one()
    base = {
        "customer_id": delivered["customer_id"],
        "fault_code": "BROKEN",
        "issue_description": "Damaged panel",
    }
    assert support.post("/api/v1/tickets", json=base).status_code == 422
    assert (
        support.post(
            "/api/v1/tickets",
            json={**base, "order_item_id": item.id, "serialized_unit_id": delivered["unit_id"]},
        ).status_code
        == 422
    )
    response = support.post("/api/v1/tickets", json={**base, "order_item_id": item.id})
    assert response.status_code == 201, response.text
    assert response.json()["under_warranty"] is True
    other = Customer(full_name="Other Customer", phone_e164="+919123451234")
    db.add(other)
    db.commit()
    response = support.post(
        "/api/v1/tickets",
        json={**base, "customer_id": other.id, "serialized_unit_id": delivered["unit_id"]},
    )
    assert response.status_code == 422


def test_failed_charge_insert_rolls_back_parts_and_ticket(db, support, delivered, monkeypatch):
    ticket = _create_ticket(support, delivered)
    _assign(support, ticket["id"], _user(db, UserRole.TECHNICIAN))
    product = db.scalars(select(Product).where(Product.sku == "CON-MC4")).one()
    stock = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).one()
    before = stock.quantity_on_hand

    def fail_charge(*args, **kwargs):
        raise RuntimeError("simulated charge failure")

    monkeypatch.setattr(ticket_repo, "add_charge", fail_charge)
    with pytest.raises(RuntimeError, match="simulated charge failure"):
        _resolve(support, ticket["id"], [{"product_id": product.id, "qty": "2"}])
    db.expire_all()
    assert stock.quantity_on_hand == before
    assert db.get(SupportTicket, ticket["id"]).status == "assigned"
    assert (
        db.scalar(
            select(func.count())
            .select_from(StockMovement)
            .where(
                StockMovement.reference_type == "ticket", StockMovement.reference_id == ticket["id"]
            )
        )
        == 0
    )
