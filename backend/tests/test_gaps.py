"""Frontend wiring gaps: permitted fields, access, files and session defaults."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from test_quotes import _user
from test_tickets import _create_ticket

from app.core.config import Settings
from app.core.enums import UserRole
from app.models.catalog import Product
from app.models.dashboard import DashboardShareLink
from app.models.inventory import Inventory, SerializedUnit
from app.models.subsidies import SubsidyDocument
from app.services import dashboard

pytest_plugins = ["test_subsidies", "test_tickets"]


@pytest.mark.parametrize("role", [UserRole.SUPPORT, UserRole.TECHNICIAN, UserRole.OFFICE,
                                 UserRole.WAREHOUSE, UserRole.DIRECTOR])
def test_products_safe_search_stock_and_pagination(db, api, role):
    client = api(_user(db, role))
    product = db.scalars(select(Product).where(Product.tracks_serial.is_(True))).first()
    response = client.get("/api/v1/products", params={"search": product.sku,
                                                    "requires_serial": True})
    assert response.status_code == 200, response.text
    item = next(x for x in response.json()["items"] if x["id"] == product.id)
    assert set(item) == {"id", "sku", "name", "category", "sale_price", "gst_percent",
                         "requires_serial", "in_stock"}
    expected = len(db.scalars(select(SerializedUnit).where(
        SerializedUnit.product_id == product.id, SerializedUnit.status == "in_stock")).all())
    assert Decimal(item["in_stock"]) == expected
    by_name = client.get("/api/v1/products", params={"search": product.name.lower()}).json()
    assert product.id in [x["id"] for x in by_name["items"]]
    bulk = db.scalars(select(Product).where(Product.tracks_serial.is_(False))).first()
    inventory = db.scalars(select(Inventory).where(Inventory.product_id == bulk.id)).first()
    result = client.get("/api/v1/products", params={"search": bulk.sku,
                                                  "requires_serial": False}).json()
    row = next(x for x in result["items"] if x["id"] == bulk.id)
    assert Decimal(row["in_stock"]) == (inventory.quantity_on_hand if inventory else 0)
    assert client.get("/api/v1/products", params={"search": "NO-SUCH-PRODUCT"}).json()["total"] == 0
    first = client.get("/api/v1/products", params={"page_size": 1}).json()
    second = client.get("/api/v1/products", params={"page_size": 1, "page": 2}).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]


def test_office_reads_tickets_without_new_write_permissions(db, api, support, delivered):
    ticket = _create_ticket(support, delivered)
    client = api(_user(db, UserRole.OFFICE))
    assert ticket["id"] in [x["id"] for x in client.get("/api/v1/tickets").json()["items"]]
    path = f"/api/v1/tickets/{ticket['id']}"
    assert client.get(path).status_code == 200
    for action in ["assign", "resolve", "replace-unit"]:
        assert client.post(path + "/" + action, json={}).status_code == 403


def test_subsidy_download_content_missing_file_and_roles(db, api, subsidy, monkeypatch):
    path = f"/api/v1/subsidies/{subsidy['id']}/documents/id_proof/file"
    client = subsidy["client"]
    missing = client.get(path)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    content = b"%PDF-1.4 test document"
    upload = client.post(path, files={"file": ("proof.pdf", content, "application/pdf")})
    assert upload.status_code == 200
    for role in [UserRole.OFFICE, UserRole.DIRECTOR]:
        response = api(_user(db, role)).get(path)
        assert response.status_code == 200
        assert response.content == content
        assert response.headers["content-type"] == "application/pdf"
    assert api(_user(db, UserRole.SUPPORT)).get(path).status_code == 403
    assert client.get("/api/v1/subsidies/999999/documents/id_proof/file").status_code == 404
    doc = db.scalars(select(SubsidyDocument).where(
        SubsidyDocument.application_id == subsidy["id"], SubsidyDocument.doc_type == "id_proof"
    )).one()
    doc.storage_key = "2000/01/missing.pdf"
    db.commit()
    assert client.get(path).json()["error"]["code"] == "not_found"


def test_share_list_active_only_safe_fields_and_roles(db, api, monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr(dashboard, "_now", lambda: now)
    client = api(_user(db, UserRole.DIRECTOR))
    ids = []
    for _ in range(3):
        r = client.post("/api/v1/dashboard/share", json={"period": "month", "expires_in_hours": 1})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    db.get(DashboardShareLink, ids[1]).expires_at = now
    db.get(DashboardShareLink, ids[2]).revoked_at = now - timedelta(seconds=1)
    db.commit()
    result = client.get("/api/v1/dashboard/share").json()
    assert result["total"] == 1
    assert [r["id"] for r in result["items"]] == [ids[0]]
    assert set(result["items"][0]) == {"id", "period", "expires_at", "created_at"}
    assert client.get("/api/v1/dashboard/share?page=2&page_size=1").json()["items"] == []
    assert api(_user(db, UserRole.OFFICE)).get("/api/v1/dashboard/share").status_code == 403


def test_shift_session_default_and_examples():
    from pathlib import Path

    assert Settings.model_fields["jwt_expire_minutes"].default == 480
    # Examples are checked in the workspace; container only mounts backend.
    root = Path(__file__).resolve().parents[2]
    for path in root.glob(".env*example"):
        assert "JWT_EXPIRE_MINUTES=480" in path.read_text()
