"""Stock receiving: serial rules, inventory, movements and cost price on PostgreSQL."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_quotes import _user

from app.core.enums import UserRole
from app.models.auth import AuditLog
from app.models.catalog import Product
from app.models.inventory import Inventory, SerializedUnit, StockMovement, StockReceipt

pytest_plugins = ["test_quotes"]


@pytest.fixture
def warehouse(db, api):
    return api(_user(db, UserRole.WAREHOUSE))


@pytest.fixture
def products(db):
    rows = {
        p.sku: p for p in db.scalars(select(Product).where(Product.sku.in_(["INV-1K", "CON-MC4"])))
    }
    costs = {sku: p.cost_price for sku, p in rows.items()}
    yield rows
    for sku, product in rows.items():
        db.refresh(product)
        product.cost_price = costs[sku]
    db.commit()


def _serial():
    return f"RCV-{uuid4().hex.upper()}"


def _body(lines):
    return {
        "supplier_name": "Hyderabad Solar Traders",
        "supplier_invoice_ref": f"HST-{uuid4().hex[:8]}",
        "received_on": date.today().isoformat(),
        "lines": lines,
    }


def _error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_serial_count_mismatch_is_422(warehouse, products):
    line = {"product_id": products["INV-1K"].id, "qty": "2", "unit_cost": "9000.00"}
    _error(
        warehouse.post("/api/v1/stock/receipts", json=_body([line])), 422, "SERIAL_COUNT_MISMATCH"
    )
    line["serials"] = [_serial()]
    _error(
        warehouse.post("/api/v1/stock/receipts", json=_body([line])), 422, "SERIAL_COUNT_MISMATCH"
    )


def test_duplicate_serial_in_request_is_422(warehouse, products):
    serial = _serial()
    line = {
        "product_id": products["INV-1K"].id,
        "qty": "2",
        "unit_cost": "9000.00",
        "serials": [serial, serial.lower()],
    }
    response = warehouse.post("/api/v1/stock/receipts", json=_body([line]))
    assert response.status_code == 422, response.text


def test_existing_serial_is_409_and_nothing_saved(db, warehouse, products):
    taken = SerializedUnit(product_id=products["INV-1K"].id, serial_number=_serial())
    db.add(taken)
    db.commit()
    fresh = _serial()
    body = _body(
        [
            {
                "product_id": products["INV-1K"].id,
                "qty": "2",
                "unit_cost": "9000.00",
                "serials": [fresh, taken.serial_number.lower()],
            }
        ]
    )
    response = warehouse.post("/api/v1/stock/receipts", json=body)
    _error(response, 409, "SERIAL_EXISTS")
    assert taken.serial_number in response.json()["error"]["message"]
    assert (
        db.scalars(select(SerializedUnit).where(SerializedUnit.serial_number == fresh)).first()
        is None
    )
    assert (
        db.scalars(
            select(StockReceipt).where(
                StockReceipt.supplier_invoice_ref == body["supplier_invoice_ref"]
            )
        ).first()
        is None
    )


def test_receipt_adds_stock_movements_and_cost_price(db, api, warehouse, products):
    inverter, connector = products["INV-1K"], products["CON-MC4"]
    stock = db.scalars(select(Inventory).where(Inventory.product_id == connector.id)).first()
    before = stock.quantity_on_hand if stock else Decimal("0")
    serials = [_serial(), _serial()]
    response = warehouse.post(
        "/api/v1/stock/receipts",
        json=_body(
            [
                {
                    "product_id": inverter.id,
                    "qty": "2",
                    "unit_cost": "9100.50",
                    "serials": [" " + serials[0].lower(), serials[1]],
                },
                {"product_id": connector.id, "qty": "40", "unit_cost": "65.25"},
            ]
        ),
    )
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["receipt_number"] == f"RCV-{receipt['id']:06d}"
    assert receipt["total"] == "20811.00"  # 2 x 9100.50 + 40 x 65.25
    db.expire_all()
    units = db.scalars(
        select(SerializedUnit).where(SerializedUnit.serial_number.in_(serials))
    ).all()
    assert len(units) == 2 and all(u.status == "in_stock" for u in units)
    stock = db.scalars(select(Inventory).where(Inventory.product_id == connector.id)).one()
    assert stock.quantity_on_hand == before + 40
    movements = db.scalars(
        select(StockMovement).where(
            StockMovement.reference_type == "stock_receipt",
            StockMovement.reference_id == receipt["id"],
        )
    ).all()
    assert sorted((m.product_id, m.quantity_delta, m.reason) for m in movements) == sorted(
        [(inverter.id, Decimal("2"), "purchase"), (connector.id, Decimal("40"), "purchase")]
    )
    assert db.get(Product, inverter.id).cost_price == Decimal("9100.50")
    assert db.get(Product, connector.id).cost_price == Decimal("65.25")
    assert (
        db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "stock_receipt", AuditLog.entity_id == receipt["id"]
            )
        )
        .one()
        .action
        == "stock.received"
    )
    assert warehouse.get(f"/api/v1/stock/receipts/{receipt['id']}").json() == receipt
    listed = warehouse.get(
        "/api/v1/stock/receipts", params={"from": date.today().isoformat()}
    ).json()
    assert any(row["id"] == receipt["id"] for row in listed["items"])
    office = api(_user(db, UserRole.OFFICE))
    rows = office.get("/api/v1/stock", params={"page_size": 100}).json()["items"]
    row = next(row for row in rows if row["sku"] == "CON-MC4")
    assert Decimal(row["on_hand"]) == before + 40
    assert all(row["category"] != "service" for row in rows)


def test_receipt_roles_and_validation(db, api, warehouse, products):
    office = api(_user(db, UserRole.OFFICE))
    line = {"product_id": products["CON-MC4"].id, "qty": "1", "unit_cost": "10.00"}
    assert office.post("/api/v1/stock/receipts", json=_body([line])).status_code == 403
    assert office.get("/api/v1/stock/receipts").status_code == 403
    for bad in ({"unit_cost": "0"}, {"qty": "0"}, {"serials": [_serial()]}):
        response = warehouse.post("/api/v1/stock/receipts", json=_body([{**line, **bad}]))
        assert response.status_code == 422, response.text
