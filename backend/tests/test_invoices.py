"""GST invoices: gapless numbers, CGST/SGST vs IGST, auto-create on delivery and paid repairs."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from test_dispatch import _scan_all, _send
from test_quotes import _create, _package_id, _survey, _user
from test_tickets import _create_ticket, _expire, _resolve

from app.core.enums import PackageType, UserRole
from app.db.session import SessionLocal
from app.models.customers import Site
from app.models.invoices import Invoice, InvoiceItem
from app.models.orders import Order
from app.models.quotes import Quote
from app.services import invoices as invoice_service

pytest_plugins = ["test_dispatch"]


@pytest.fixture
def support(db, api):
    return api(_user(db, UserRole.SUPPORT))


def _deliver(db, warehouse, pick, state="Maharashtra"):
    order = db.get(Order, pick["order_id"])
    db.get(Site, order.site_id).state = state
    db.commit()
    _scan_all(warehouse, pick)
    assert _send(warehouse, pick).status_code == 200
    response = warehouse.post(
        f"/api/v1/dispatches/{pick['id']}/deliver", json={"receiver_name": "Ravi Kumar"}
    )
    assert response.status_code == 200, response.text
    return order


def _invoices_for_order(db, order_id):
    db.expire_all()
    return db.scalars(select(Invoice).where(Invoice.order_id == order_id)).all()


def _accepted_order_id(db, api, office) -> int:
    client = api(office)
    quote = _create(client, _survey(db).id, _package_id(db, PackageType.PANEL_SET, 1))
    client.post(f"/api/v1/quotes/{quote['id']}/send")
    return client.post(f"/api/v1/quotes/{quote['id']}/accept").json()["order_id"]


# ---------------------------------------------------------------- Pure rules

def test_financial_year_and_gst_split():
    assert invoice_service.financial_year(date(2026, 11, 1)) == "2026-27"
    assert invoice_service.financial_year(date(2027, 3, 31)) == "2026-27"
    assert invoice_service.financial_year(date(2027, 4, 1)) == "2027-28"
    assert invoice_service.split_gst(Decimal("101.01"), " telangana ") == (
        Decimal("50.51"), Decimal("50.50"), Decimal("0.00")
    )
    assert invoice_service.split_gst(Decimal("101.01"), "Karnataka") == (
        Decimal("0.00"), Decimal("0.00"), Decimal("101.01")
    )


# ---------------------------------------------------------------- Order invoices

def test_delivery_creates_one_invoice_equal_to_order_igst_out_of_state(
    db, api, office, warehouse, pick
):
    order = _deliver(db, warehouse, pick, "Karnataka")
    invoices = _invoices_for_order(db, order.id)
    assert len(invoices) == 1
    invoice = invoices[0]
    quote = db.get(Quote, order.quote_id)
    assert (invoice.subtotal, invoice.tax_total, invoice.total) == (
        quote.subtotal, quote.tax_total, quote.total
    )
    assert (invoice.cgst, invoice.sgst, invoice.igst) == (
        Decimal("0.00"), Decimal("0.00"), quote.tax_total
    )
    assert invoice.invoice_number.startswith(f"INV/{invoice.financial_year}/")
    lines = db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice.id)).all()
    assert sum(line.taxable for line in lines) == quote.subtotal
    assert sum(line.gst_amount for line in lines) == quote.tax_total

    printed = api(office).get(f"/api/v1/invoices/{invoice.id}")
    assert printed.status_code == 200, printed.text
    body = printed.json()
    assert body["seller"]["state"] == "Telangana"
    assert body["place_of_supply"] == "Karnataka"
    assert body["order_number"] == order.order_number
    assert body["amount_paid"] == "1000.00"
    assert Decimal(body["balance_due"]) == quote.total - Decimal("1000.00")

    listed = api(office).get("/api/v1/invoices", params={"search": invoice.invoice_number})
    assert [row["id"] for row in listed.json()["items"]] == [invoice.id]
    assert api(_user(db, UserRole.WAREHOUSE)).get("/api/v1/invoices").status_code == 403


def test_telangana_split_is_exact(db, warehouse, pick):
    order = _deliver(db, warehouse, pick, "Telangana")
    invoice = _invoices_for_order(db, order.id)[0]
    assert invoice.igst == Decimal("0.00")
    assert invoice.cgst + invoice.sgst == invoice.tax_total
    assert invoice.cgst - invoice.sgst in (Decimal("0.00"), Decimal("0.01"))


def test_numbers_are_consecutive_and_reset_each_financial_year(db, api, office):
    orders = [db.get(Order, _accepted_order_id(db, api, office)) for _ in range(4)]
    actor = _user(db, UserRole.OFFICE)
    session = SessionLocal()
    try:
        made = [
            invoice_service.create_for_order(
                session, session.get(Order, o.id), actor=actor, invoice_date=date(2026, 11, 1)
            )[0]
            for o in orders[:3]
        ]
        numbers = [int(i.invoice_number.rsplit("/", 1)[1]) for i in made]
        assert all(i.invoice_number.startswith("INV/2026-27/") for i in made)
        assert numbers == [numbers[0], numbers[0] + 1, numbers[0] + 2]

        next_year, _ = invoice_service.create_for_order(
            session, session.get(Order, orders[3].id), actor=actor, invoice_date=date(2027, 4, 1)
        )
        assert next_year.invoice_number == "INV/2027-28/000001"
    finally:
        session.rollback()  # gapless: the rollback gives the numbers back
        session.close()

    session = SessionLocal()
    try:
        again, _ = invoice_service.create_for_order(
            session, session.get(Order, orders[0].id), actor=actor, invoice_date=date(2026, 11, 1)
        )
        assert int(again.invoice_number.rsplit("/", 1)[1]) == numbers[0]
    finally:
        session.rollback()
        session.close()


def test_backfill_endpoint_idempotent_and_needs_delivery(db, api, office, warehouse, pick):
    client = api(office)
    pending = _accepted_order_id(db, api, office)
    response = client.post(f"/api/v1/orders/{pending}/invoice")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ORDER_NOT_DELIVERED"

    order = _deliver(db, warehouse, pick)
    first = client.post(f"/api/v1/orders/{order.id}/invoice")
    second = client.post(f"/api/v1/orders/{order.id}/invoice")
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(_invoices_for_order(db, order.id)) == 1


# ---------------------------------------------------------------- Service invoices

def _close(support, ticket_id):
    response = support.post(
        f"/api/v1/tickets/{ticket_id}/confirm",
        json={"confirmed": True, "customer_name": "Ravi Kumar"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _repair(db, api, support, delivered, *, expired: bool):
    if expired:
        _expire(db, delivered)
    ticket = _create_ticket(support, delivered)
    tech = _user(db, UserRole.TECHNICIAN)
    assign = support.post(
        f"/api/v1/tickets/{ticket['id']}/assign",
        json={"technician_id": tech.id, "visit_date": date.today().isoformat()},
    )
    assert assign.status_code == 200, assign.text
    resolved = _resolve(api(tech), ticket["id"], hours="1.50")
    assert resolved.status_code == 200, resolved.text
    return _close(support, ticket["id"])


@pytest.fixture
def delivered(db, warehouse, pick):
    order = _deliver(db, warehouse, pick)
    return {**pick, "customer_id": order.customer_id, "unit_id": pick["serials"]["INV-1K"].id}


def test_paid_repair_gets_service_invoice_warranty_repair_none(db, api, support, delivered):
    warranty_ticket = _repair(db, api, support, delivered, expired=False)
    assert db.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.ticket_id == warranty_ticket["id"])
    ) == 0

    paid = _repair(db, api, support, delivered, expired=True)
    db.expire_all()
    invoice = db.scalars(select(Invoice).where(Invoice.ticket_id == paid["id"])).one()
    assert invoice.kind == "service"
    assert str(invoice.total) == paid["total"]
    assert str(invoice.tax_total) == paid["gst"]
    assert invoice.igst == invoice.tax_total  # site is in Maharashtra
