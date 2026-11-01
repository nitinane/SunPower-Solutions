"""Warranty replacement of a serialized unit on PostgreSQL."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from test_quotes import _user
from test_tickets import _assign, _create_ticket, _expire, _resolve

from app.core.dates import add_months
from app.core.enums import UserRole
from app.models.catalog import Product
from app.models.inventory import SerializedUnit, StockMovement
from app.models.warranties import Warranty

pytest_plugins = ["test_tickets"]


def _today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def _unit(db, sku, status="in_stock"):
    product = db.scalars(select(Product).where(Product.sku == sku)).one()
    unit = SerializedUnit(
        product_id=product.id, serial_number=f"NEW-{uuid4().hex.upper()}", status=status
    )
    db.add(unit)
    db.commit()
    return unit


def _replace(client, ticket_id, serial):
    return client.post(f"/api/v1/tickets/{ticket_id}/replace-unit", json={"new_serial": serial})


def _error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


@pytest.fixture
def tech(db):
    return _user(db, UserRole.TECHNICIAN)


def test_wrong_product_missing_and_not_in_stock(db, api, support, delivered, tech):
    ticket = _create_ticket(support, delivered)
    _error(
        _replace(support, ticket["id"], _unit(db, "INV-1K").serial_number),
        409,
        "TICKET_STATUS_INVALID",
    )
    _assign(support, ticket["id"], tech)
    client = api(tech)
    _error(
        _replace(client, ticket["id"], _unit(db, "BAT-150AH").serial_number),
        409,
        "SERIAL_WRONG_PRODUCT",
    )
    _error(_replace(client, ticket["id"], "NOPE-" + uuid4().hex), 404, "SERIAL_NOT_FOUND")
    shipped = _unit(db, "INV-1K", status="dispatched")
    _error(_replace(client, ticket["id"], shipped.serial_number), 409, "SERIAL_NOT_IN_STOCK")
    other = api(_user(db, UserRole.TECHNICIAN))
    assert _replace(other, ticket["id"], _unit(db, "INV-1K").serial_number).status_code == 403


def test_under_warranty_swap_is_free_and_keeps_end_date(db, api, support, delivered, tech):
    old_warranty = db.scalars(
        select(Warranty).where(Warranty.serialized_unit_id == delivered["unit_id"])
    ).one()
    ticket = _create_ticket(support, delivered)
    _assign(support, ticket["id"], tech)
    new = _unit(db, "INV-1K")
    response = _replace(api(tech), ticket["id"], " " + new.serial_number.lower())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == body["parts_subtotal"] == body["gst"] == "0.00"
    charge = next(c for c in body["charges"] if c["replacement_unit_id"] == new.id)
    product = db.get(Product, new.product_id)
    assert charge["customer_price"] == "0.00" and charge["covered_by_warranty"]
    assert Decimal(charge["cost_amount"]) == product.cost_price
    assert body["history"][-1]["action"] == "unit.replaced"
    assert body["history"][-1]["new_data"]["serial"] == new.serial_number
    db.expire_all()
    new_warranty = db.scalars(select(Warranty).where(Warranty.serialized_unit_id == new.id)).one()
    assert new_warranty.end_date == old_warranty.end_date
    assert new_warranty.start_date == _today()
    assert db.get(Warranty, old_warranty.id).replaced_by_warranty_id == new_warranty.id
    assert db.get(SerializedUnit, delivered["unit_id"]).status == "returned"
    assert db.get(SerializedUnit, new.id).status == "dispatched"
    movement = db.scalars(
        select(StockMovement).where(
            StockMovement.reference_type == "ticket",
            StockMovement.reference_id == ticket["id"],
            StockMovement.product_id == new.product_id,
        )
    ).one()
    assert movement.quantity_delta == Decimal("-1") and movement.reason == "service"
    results = support.get("/api/v1/support/search", params={"q": new.serial_number}).json()
    result = next(r for r in results if r["customer"]["id"] == delivered["customer_id"])
    serials = {u["serial"]: u for u in result["units"]}
    assert serials[new.serial_number]["warranty_status"] == "active"
    assert delivered["serials"]["INV-1K"].serial_number not in serials
    again = _replace(api(tech), ticket["id"], _unit(db, "INV-1K").serial_number)
    _error(again, 409, "UNIT_ALREADY_REPLACED")
    # The new unit can get its own ticket later.
    later = support.post(
        "/api/v1/tickets",
        json={
            "customer_id": delivered["customer_id"],
            "serialized_unit_id": new.id,
            "fault_code": None,
            "issue_description": "Fan noise",
        },
    )
    assert later.status_code == 201, later.text
    assert later.json()["under_warranty"] is True


def test_out_of_warranty_swap_billed_with_full_new_warranty(db, support, delivered, tech):
    _expire(db, delivered)
    ticket = _create_ticket(support, delivered)
    _assign(support, ticket["id"], tech)
    new = _unit(db, "INV-1K")
    product = db.get(Product, new.product_id)
    response = _replace(support, ticket["id"], new.serial_number)
    assert response.status_code == 200, response.text
    body = response.json()
    gst = (product.sale_price * product.gst_rate / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
    assert Decimal(body["parts_subtotal"]) == product.sale_price
    assert Decimal(body["gst"]) == gst
    assert Decimal(body["total"]) == product.sale_price + gst
    charge = next(c for c in body["charges"] if c["replacement_unit_id"] == new.id)
    assert Decimal(charge["customer_price"]) == product.sale_price
    assert not charge["covered_by_warranty"]
    db.expire_all()
    warranty = db.scalars(select(Warranty).where(Warranty.serialized_unit_id == new.id)).one()
    assert warranty.start_date == _today()
    assert warranty.end_date == add_months(_today(), product.warranty_months)
    resolved = _resolve(support, ticket["id"], hours="0")
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["total"] == body["total"]
