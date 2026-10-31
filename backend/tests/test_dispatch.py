"""Serial scanning, transactional stock out, and delivery warranties on PostgreSQL."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_quotes import _create, _package_id, _survey, _user

from app.core.enums import PackageType, UserRole
from app.models.auth import AuditLog
from app.models.catalog import Product
from app.models.dispatch import Dispatch
from app.models.inventory import Inventory, SerializedUnit, StockMovement
from app.models.orders import Order
from app.models.warranties import Warranty
from app.repositories import warranties as warranty_repo
from scripts.seed import seed_stock

pytest_plugins = ["test_quotes"]


@pytest.fixture
def warehouse(db, api):
    return api(_user(db, UserRole.WAREHOUSE))


@pytest.fixture
def pick(db, api, office, warehouse):
    client = api(office)
    quote = _create(client, _survey(db).id, _package_id(db, PackageType.ON_GRID, 1), True)
    assert client.post(f"/api/v1/quotes/{quote['id']}/send").status_code == 200
    order_id = client.post(f"/api/v1/quotes/{quote['id']}/accept").json()["order_id"]
    payment = client.post(
        f"/api/v1/orders/{order_id}/payments",
        json={
            "amount": "1000.00",
            "method": "cash",
        },
    )
    assert payment.status_code == 201, payment.text
    dispatch_id = payment.json()["order"]["pick_list"]["id"]
    details = warehouse.get(f"/api/v1/dispatches/{dispatch_id}")
    assert details.status_code == 200, details.text
    # Fresh units per test; tests currently share the dev DB (until P3-1).
    serials = {}
    for line in details.json()["lines"]:
        product = db.scalars(select(Product).where(Product.sku == line["sku"])).one()
        if product.category == "service":
            continue
        if product.tracks_serial:
            unit = SerializedUnit(
                product_id=product.id, serial_number=f"TEST-{uuid4().hex.upper()}"
            )
            db.add(unit)
            db.flush()
            serials[line["sku"]] = unit
        else:
            stock = db.scalars(
                select(Inventory).where(Inventory.product_id == product.id).with_for_update()
            ).first()
            if stock is None:
                stock = Inventory(product_id=product.id)
                db.add(stock)
            stock.quantity_on_hand = Decimal("10000")
            stock.quantity_reserved = Decimal("0")
    db.commit()
    return {"id": dispatch_id, "order_id": order_id, "detail": details.json(), "serials": serials}


def _scan(warehouse, pick, serial):
    return warehouse.post(f"/api/v1/dispatches/{pick['id']}/scan", json={"serial": serial})


def _scan_all(warehouse, pick):
    for unit in pick["serials"].values():
        response = _scan(warehouse, pick, unit.serial_number)
        assert response.status_code == 200, response.text


def _send(warehouse, pick):
    return warehouse.post(f"/api/v1/dispatches/{pick['id']}/send")


def _error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


def test_unknown_and_wrong_product_serial(db, warehouse, pick):
    _error(_scan(warehouse, pick, "UNKNOWN-" + uuid4().hex), 404, "SERIAL_NOT_FOUND")
    product = db.scalars(select(Product).where(Product.sku == "BAT-150AH")).one()
    unit = SerializedUnit(product_id=product.id, serial_number=f"BAT-{uuid4().hex.upper()}")
    db.add(unit)
    db.commit()
    response = _scan(warehouse, pick, unit.serial_number)
    _error(response, 409, "SERIAL_WRONG_PRODUCT")
    assert "BAT-150AH" in response.json()["error"]["message"]
    assert "INV-1K" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("dispatched", "SERIAL_ALREADY_SHIPPED"),
        ("reserved", "SERIAL_NOT_IN_STOCK"),
    ],
)
def test_unavailable_serial(db, warehouse, pick, status, code):
    unit = pick["serials"]["INV-1K"]
    unit.status = status
    db.commit()
    _error(_scan(warehouse, pick, unit.serial_number), 409, code)


def test_scan_normalized_idempotent_and_line_limit(db, warehouse, pick):
    unit = pick["serials"]["INV-1K"]
    response = _scan(warehouse, pick, " " + unit.serial_number.lower() + " ")
    assert response.status_code == 200, response.text
    again = _scan(warehouse, pick, unit.serial_number)
    assert again.status_code == 200
    line = next(line for line in again.json()["lines"] if line["sku"] == "INV-1K")
    assert line["scanned"] == 1
    assert len(line["serials"]) == 1
    extra = SerializedUnit(product_id=unit.product_id, serial_number=f"EXTRA-{uuid4().hex.upper()}")
    db.add(extra)
    db.commit()
    _error(_scan(warehouse, pick, extra.serial_number), 409, "LINE_ALREADY_COMPLETE")


def test_unscan_only_own_item_and_only_before_send(db, warehouse, pick):
    _scan_all(warehouse, pick)
    response = warehouse.get(f"/api/v1/dispatches/{pick['id']}")
    line = next(line for line in response.json()["lines"] if line["sku"] == "INV-1K")
    item_id = line["serials"][0]["dispatch_item_id"]
    response = warehouse.delete(f"/api/v1/dispatches/{pick['id']}/scan/{item_id}")
    assert response.status_code == 200, response.text
    _error(_send(warehouse, pick), 409, "SCAN_INCOMPLETE")
    _error(warehouse.delete(f"/api/v1/dispatches/{pick['id']}/scan/{item_id}"), 404, "not_found")
    assert _scan(warehouse, pick, pick["serials"]["INV-1K"].serial_number).status_code == 200
    assert _send(warehouse, pick).status_code == 200
    response = warehouse.delete(f"/api/v1/dispatches/{pick['id']}/scan/{item_id}")
    _error(response, 409, "DISPATCH_LOCKED")


def test_send_blocked_until_all_scanned(db, warehouse, pick):
    response = _send(warehouse, pick)
    _error(response, 409, "SCAN_INCOMPLETE")
    assert "0/1" in response.json()["error"]["message"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(StockMovement)
            .where(
                StockMovement.reference_id == pick["id"],
                StockMovement.reference_type == "dispatch",
            )
        )
        == 0
    )


def test_send_deducts_bulk_and_moves_every_product(db, warehouse, pick):
    _scan_all(warehouse, pick)
    expected = {}
    before = {}
    for line in pick["detail"]["lines"]:
        if line["sku"] == "SVC-INSTALL":
            continue
        product = db.scalars(select(Product).where(Product.sku == line["sku"])).one()
        expected[product.id] = -Decimal(line["qty"])
        if not line["requires_serial"]:
            before[product.id] = (
                db.scalars(select(Inventory).where(Inventory.product_id == product.id))
                .one()
                .quantity_on_hand
            )
    response = _send(warehouse, pick)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "dispatched"
    assert response.json()["dispatched_at"] is not None
    db.expire_all()
    assert db.get(Order, pick["order_id"]).status == "dispatched"
    movements = db.scalars(
        select(StockMovement).where(
            StockMovement.reference_type == "dispatch",
            StockMovement.reference_id == pick["id"],
        )
    ).all()
    assert {row.product_id: row.quantity_delta for row in movements} == expected
    assert len(movements) == len(expected)
    assert all(row.reason == "dispatch" for row in movements)
    for pid, quantity in before.items():
        stock = db.scalars(select(Inventory).where(Inventory.product_id == pid)).one()
        assert stock.quantity_on_hand == quantity + expected[pid]
    assert all(unit.status == "dispatched" for unit in pick["serials"].values())
    _error(_send(warehouse, pick), 409, "DISPATCH_LOCKED")
    _error(
        _scan(warehouse, pick, next(iter(pick["serials"].values())).serial_number),
        409,
        "DISPATCH_LOCKED",
    )


def test_shortage_rolls_back_everything(db, warehouse, pick):
    _scan_all(warehouse, pick)
    product = db.scalars(select(Product).where(Product.sku == "EARTH-LA")).one()
    stock = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).one()
    stock.quantity_on_hand = Decimal("0")
    db.commit()
    before = dict(db.execute(select(Inventory.product_id, Inventory.quantity_on_hand)).all())
    response = _send(warehouse, pick)
    _error(response, 409, "INSUFFICIENT_STOCK")
    assert product.name in response.json()["error"]["message"]
    db.expire_all()
    assert (
        dict(db.execute(select(Inventory.product_id, Inventory.quantity_on_hand)).all()) == before
    )
    assert all(unit.status == "in_stock" for unit in pick["serials"].values())
    assert db.get(Order, pick["order_id"]).status == "confirmed"
    assert (
        db.scalar(
            select(func.count())
            .select_from(StockMovement)
            .where(
                StockMovement.reference_type == "dispatch",
                StockMovement.reference_id == pick["id"],
            )
        )
        == 0
    )


def test_delivery_creates_serial_and_bulk_warranties_in_ist(db, warehouse, pick):
    _scan_all(warehouse, pick)
    assert _send(warehouse, pick).status_code == 200
    response = warehouse.post(
        f"/api/v1/dispatches/{pick['id']}/deliver",
        json={
            "receiver_name": "Ravi Kumar",
            "delivered_at": "2027-01-30T20:00:00Z",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "delivered"
    assert body["receiver_name"] == "Ravi Kumar"
    # Jan 30 UTC is Jan 31 in India.
    assert all(row["start_date"] == "2027-01-31" for row in body["warranties"])
    products = {p.id: p for p in db.scalars(select(Product))}
    by_sku = {products[row["product_id"]].sku: row for row in body["warranties"]}
    assert by_sku["INV-1K"]["end_date"] == "2029-01-31"
    assert by_sku["INV-1K"]["serialized_unit_id"] == pick["serials"]["INV-1K"].id
    assert by_sku["PNL-540"]["end_date"] == "2047-01-31"
    assert by_sku["PNL-540"]["serialized_unit_id"] is None
    assert by_sku["PNL-540"]["quantity"] == "2.000"
    assert "SVC-INSTALL" not in by_sku
    assert body["warranties_created"] == len(body["warranties"]) == 12
    again = warehouse.post(
        f"/api/v1/dispatches/{pick['id']}/deliver", json={"receiver_name": "Ravi Kumar"}
    )
    _error(again, 409, "ALREADY_DELIVERED")
    db.expire_all()
    assert db.get(Order, pick["order_id"]).status == "delivered"
    assert (
        db.scalar(
            select(func.count())
            .select_from(Warranty)
            .where(
                Warranty.order_id == pick["order_id"],
            )
        )
        == 12
    )
    audit = db.scalars(
        select(AuditLog).where(
            AuditLog.entity_type == "dispatch",
            AuditLog.entity_id == pick["id"],
            AuditLog.action == "warranty.created",
        )
    ).one()
    assert audit.new_data["count"] == 12


def test_delivery_requires_sent_and_valid_input(warehouse, pick):
    response = warehouse.post(
        f"/api/v1/dispatches/{pick['id']}/deliver", json={"receiver_name": "Ravi Kumar"}
    )
    _error(response, 409, "DISPATCH_LOCKED")
    for body in (
        {"receiver_name": " "},
        {"receiver_name": "Ravi Kumar", "delivered_at": "2027-01-31T10:00:00"},
    ):
        response = warehouse.post(f"/api/v1/dispatches/{pick['id']}/deliver", json=body)
        assert response.status_code == 422


def test_office_cannot_use_warehouse_routes(api, office, pick):
    client = api(office)
    prefix = f"/api/v1/dispatches/{pick['id']}"
    for response in (
        client.get("/api/v1/dispatches"),
        client.get(prefix),
        client.post(prefix + "/scan", json={"serial": "INV-1K-0001"}),
        client.delete(prefix + "/scan/1"),
        client.post(prefix + "/send"),
        client.post(prefix + "/deliver", json={"receiver_name": "Ravi Kumar"}),
    ):
        assert response.status_code == 403


def test_queue_filter_and_oldest_first(warehouse, pick):
    response = warehouse.get("/api/v1/dispatches", params={"status": "draft", "page_size": 100})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    assert all(item["status"] == "draft" for item in body["items"])
    assert [item["id"] for item in body["items"]] == sorted(item["id"] for item in body["items"])
    assert warehouse.get("/api/v1/dispatches", params={"page_size": 101}).status_code == 422


def test_serial_cannot_be_claimed_by_another_pick_list(db, api, office, warehouse, pick):
    unit = pick["serials"]["INV-1K"]
    assert _scan(warehouse, pick, unit.serial_number).status_code == 200
    client = api(office)
    quote = _create(client, _survey(db).id, _package_id(db, PackageType.ON_GRID, 1))
    assert client.post(f"/api/v1/quotes/{quote['id']}/send").status_code == 200
    order_id = client.post(f"/api/v1/quotes/{quote['id']}/accept").json()["order_id"]
    payment = client.post(
        f"/api/v1/orders/{order_id}/payments", json={"amount": "1000.00", "method": "cash"}
    )
    other_id = payment.json()["order"]["pick_list"]["id"]
    response = warehouse.post(
        f"/api/v1/dispatches/{other_id}/scan", json={"serial": unit.serial_number}
    )
    _error(response, 409, "SERIAL_ALREADY_SHIPPED")
    details = warehouse.get(f"/api/v1/dispatches/{other_id}").json()
    assert all(line["scanned"] == 0 for line in details["lines"])


def test_warranty_failure_rolls_back_delivery(db, warehouse, pick, monkeypatch):
    _scan_all(warehouse, pick)
    assert _send(warehouse, pick).status_code == 200
    create = warranty_repo.create
    calls = 0

    def fail_after_first(db, **values):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated warranty storage failure")
        return create(db, **values)

    monkeypatch.setattr(warranty_repo, "create", fail_after_first)
    with pytest.raises(RuntimeError, match="simulated warranty storage failure"):
        warehouse.post(
            f"/api/v1/dispatches/{pick['id']}/deliver", json={"receiver_name": "Ravi Kumar"}
        )
    db.expire_all()
    dispatch = db.get(Dispatch, pick["id"])
    assert dispatch.status == "dispatched"
    assert dispatch.delivered_at is None
    assert dispatch.receiver_name is None
    assert db.get(Order, pick["order_id"]).status == "dispatched"
    assert (
        db.scalar(
            select(func.count()).select_from(Warranty).where(Warranty.order_id == pick["order_id"])
        )
        == 0
    )


def test_seed_stock_idempotent_preserves_existing_stock(db):
    seed_stock(db)
    db.commit()
    before = list(
        db.execute(
            select(Inventory.product_id, Inventory.quantity_on_hand).order_by(Inventory.product_id)
        )
    )
    count = db.scalar(select(func.count()).select_from(SerializedUnit))
    seed_stock(db)
    db.commit()
    assert db.scalar(select(func.count()).select_from(SerializedUnit)) == count
    assert (
        list(
            db.execute(
                select(Inventory.product_id, Inventory.quantity_on_hand).order_by(
                    Inventory.product_id
                )
            )
        )
        == before
    )
    assert db.scalars(
        select(SerializedUnit).where(SerializedUnit.serial_number == "INV-1K-0001")
    ).one()
