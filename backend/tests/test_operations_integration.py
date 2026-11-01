"""Read-only acceptance checks against the separately populated sunpower_demo DB."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import case, func, select
from sqlalchemy.engine import make_url

from app.core.enums import PaymentStatus, PaymentType
from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import create_app
from app.models.dispatch import DispatchItem
from app.models.installations import InstallationEvidence, InstallationJob, JobTechnician
from app.models.inventory import Inventory, StockMovement
from app.models.invoices import Invoice
from app.models.orders import Order, OrderItem
from app.models.payments import Payment
from app.models.quotes import Quote
from app.models.users import User


@pytest.fixture(scope="module")
def demo_client():
    database_url = os.environ.get("SUNPOWER_OPERATIONS_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set SUNPOWER_OPERATIONS_TEST_DATABASE_URL to populated sunpower_demo.")
    if make_url(database_url).database != "sunpower_demo":
        pytest.fail("Operations integration tests only read from sunpower_demo.")
    old_bind = SessionLocal.kw["bind"]
    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    SessionLocal.configure(bind=engine)
    try:
        with SessionLocal() as db:
            admin = db.scalar(select(User).where(User.role == "admin").order_by(User.id))
            assert admin is not None
            admin_token = create_access_token(str(admin.id))
        with TestClient(create_app()) as client:
            yield client, {"Authorization": f"Bearer {admin_token}"}
    finally:
        SessionLocal.configure(bind=old_bind)
        engine.dispose()


def test_customer_pagination_search_and_real_relationships(demo_client) -> None:
    client, headers = demo_client
    pages = [
        client.get("/api/v1/customers", params={"page": page, "page_size": 100}, headers=headers)
        for page in (1, 2, 3)
    ]
    assert all(response.status_code == 200 for response in pages)
    assert sum(len(response.json()["items"]) for response in pages) == 300
    first = pages[0].json()["items"][0]
    search = client.get("/api/v1/customers", params={"search": first["full_name"]}, headers=headers)
    assert search.status_code == 200
    assert any(item["id"] == first["id"] for item in search.json()["items"])
    detail = client.get(f"/api/v1/customers/{first['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["sites"]


def test_operations_reads_reconcile_inventory_and_dispatch(demo_client) -> None:
    client, headers = demo_client
    installations = client.get("/api/v1/installations", headers=headers)
    inventory = client.get("/api/v1/inventory", headers=headers)
    movements = client.get("/api/v1/inventory/movements", headers=headers)
    dispatches = client.get("/api/v1/inventory/dispatches", headers=headers)
    assert installations.status_code == inventory.status_code == movements.status_code == 200
    assert dispatches.status_code == 200
    with SessionLocal() as db:
        evidence = db.scalar(select(InstallationEvidence).order_by(InstallationEvidence.id))
        assert evidence is not None
        evidence_response = client.get(
            f"/api/v1/installations/{evidence.job_id}/evidence/{evidence.id}", headers=headers
        )
        assert evidence_response.status_code == 200
        assert evidence_response.content
        available = dict(
            db.execute(
                select(
                    Inventory.product_id, Inventory.quantity_on_hand - Inventory.quantity_reserved
                )
            ).all()
        )
        movement_totals = dict(
            db.execute(
                select(StockMovement.product_id, func.sum(StockMovement.quantity_delta)).group_by(
                    StockMovement.product_id
                )
            ).all()
        )
        assert all(available[key] == movement_totals.get(key, Decimal("0")) for key in available)
        invalid_dispatch_lines = db.scalar(
            select(func.count())
            .select_from(DispatchItem)
            .outerjoin(
                OrderItem,
                (OrderItem.id == DispatchItem.order_item_id)
                & (OrderItem.product_id == DispatchItem.product_id),
            )
            .where(OrderItem.id.is_(None))
        )
        assert invalid_dispatch_lines == 0


def test_financial_totals_permissions_and_cache(demo_client) -> None:
    client, headers = demo_client
    with SessionLocal() as db:
        net_payment = case(
            (Payment.payment_type == PaymentType.REFUND, -Payment.amount),
            else_=Payment.amount,
        )
        expected_revenue = db.scalar(
            select(func.coalesce(func.sum(net_payment), Decimal("0"))).where(
                Payment.status == PaymentStatus.COMPLETED
            )
        )
        paid_orders = (
            select(Payment.order_id.label("order_id"), func.sum(net_payment).label("paid"))
            .where(Payment.order_id.is_not(None), Payment.status == PaymentStatus.COMPLETED)
            .group_by(Payment.order_id)
            .subquery()
        )
        order_due = db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        func.greatest(
                            Quote.total - func.coalesce(paid_orders.c.paid, Decimal("0")),
                            Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                )
            )
            .select_from(Order)
            .join(Quote, Quote.id == Order.quote_id)
            .outerjoin(paid_orders, paid_orders.c.order_id == Order.id)
            .where(Order.status != "cancelled")
        )
        invoice_totals = (
            select(Invoice.ticket_id.label("ticket_id"), func.sum(Invoice.total).label("total"))
            .where(Invoice.ticket_id.is_not(None), Invoice.status.not_in(["draft", "void"]))
            .group_by(Invoice.ticket_id)
            .subquery()
        )
        paid_tickets = (
            select(Payment.ticket_id.label("ticket_id"), func.sum(net_payment).label("paid"))
            .where(Payment.ticket_id.is_not(None), Payment.status == PaymentStatus.COMPLETED)
            .group_by(Payment.ticket_id)
            .subquery()
        )
        service_due = db.scalar(
            select(
                func.coalesce(
                    func.sum(
                        func.greatest(
                            invoice_totals.c.total
                            - func.coalesce(paid_tickets.c.paid, Decimal("0")),
                            Decimal("0"),
                        )
                    ),
                    Decimal("0"),
                )
            ).select_from(
                invoice_totals.outerjoin(
                    paid_tickets,
                    paid_tickets.c.ticket_id == invoice_totals.c.ticket_id,
                )
            )
        )
        support = db.scalar(select(User).where(User.role == "support").order_by(User.id))
        assert support is not None
        support_token = create_access_token(str(support.id))
        technician = db.execute(
            select(User, JobTechnician.job_id)
            .join(JobTechnician, JobTechnician.technician_id == User.id)
            .where(User.role == "technician")
            .limit(1)
        ).first()
        assert technician is not None
        technician_token = create_access_token(str(technician[0].id))
        another_job = db.scalar(
            select(InstallationJob.id)
            .where(InstallationJob.id != technician[1])
            .order_by(InstallationJob.id)
        )
    report = client.get("/api/v1/dashboard/reports", headers=headers)
    cached_report = client.get("/api/v1/dashboard/reports", headers=headers)
    assert report.status_code == cached_report.status_code == 200
    assert report.json()["total_revenue"] == str(expected_revenue)
    assert report.json()["outstanding_payments"] == str(order_due + service_due)
    assert report.json()["installation_count"] == len(report.json()["profit_per_job"])
    assert (
        client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {support_token}"}
        ).status_code
        == 403
    )
    assigned = client.get(
        f"/api/v1/installations/{technician[1]}",
        headers={"Authorization": f"Bearer {technician_token}"},
    )
    assert assigned.status_code == 200
    if another_job is not None:
        hidden = client.get(
            f"/api/v1/installations/{another_job}",
            headers={"Authorization": f"Bearer {technician_token}"},
        )
        assert hidden.status_code == 404
