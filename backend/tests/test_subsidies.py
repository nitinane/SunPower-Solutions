"""Subsidy tracking: auto-create on first payment, document checklist, step rules."""

import pytest
from sqlalchemy import func, select
from test_quotes import _create, _package_id, _survey, _user

from app.core.dates import today_ist
from app.core.enums import InstallationJobStatus, PackageType, SubsidyDocType, UserRole
from app.models.enquiries import Enquiry
from app.models.installations import InstallationJob
from app.models.subsidies import SubsidyApplication, SubsidyDocument

pytest_plugins = ["test_quotes"]

TODAY = today_ist().isoformat()
BEFORE_CERT = [d.value for d in SubsidyDocType if d != SubsidyDocType.INSTALLATION_CERTIFICATE]


def _paid_order(db, client, *, subsidy: bool, amount: str = "1000.00") -> int:
    survey = _survey(db)
    db.get(Enquiry, survey.enquiry_id).subsidy_requested = subsidy
    db.commit()
    quote = _create(client, survey.id, _package_id(db, PackageType.PANEL_SET, 1))
    client.post(f"/api/v1/quotes/{quote['id']}/send")
    order_id = client.post(f"/api/v1/quotes/{quote['id']}/accept").json()["order_id"]
    paid = client.post(
        f"/api/v1/orders/{order_id}/payments", json={"amount": amount, "method": "cash"}
    )
    assert paid.status_code == 201, paid.text
    return order_id


def _subsidy_for(db, order_id):
    return db.scalars(
        select(SubsidyApplication).where(SubsidyApplication.order_id == order_id)
    ).first()


def _error(response, status, code):
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    return response.json()["error"]


def _tick(client, sid, *docs):
    for doc in docs:
        r = client.patch(f"/api/v1/subsidies/{sid}/documents/{doc}", json={"received": True})
        assert r.status_code == 200, r.text


def _advance(client, sid, to_status, **extra):
    return client.post(
        f"/api/v1/subsidies/{sid}/advance", json={"to_status": to_status, "date": TODAY, **extra}
    )


@pytest.fixture
def subsidy(db, api, office):
    client = api(office)
    order_id = _paid_order(db, client, subsidy=True)
    return {"client": client, "order_id": order_id, "id": _subsidy_for(db, order_id).id}


def test_auto_created_on_first_payment_only_when_requested(db, api, office):
    client = api(office)
    order_id = _paid_order(db, client, subsidy=True)
    app = _subsidy_for(db, order_id)
    assert app is not None and app.status == "draft"
    docs = db.scalars(
        select(SubsidyDocument.doc_type).where(SubsidyDocument.application_id == app.id)
    ).all()
    assert sorted(docs) == sorted(d.value for d in SubsidyDocType)

    # A second payment does not create another one.
    again = client.post(
        f"/api/v1/orders/{order_id}/payments", json={"amount": "10.00", "method": "cash"}
    )
    assert again.status_code == 201, again.text
    count = db.scalar(
        select(func.count()).where(SubsidyApplication.order_id == order_id)
    )
    assert count == 1

    plain = _paid_order(db, client, subsidy=False)
    assert _subsidy_for(db, plain) is None

    # Manual create: works for the plain order, 409 when it already exists.
    created = client.post(f"/api/v1/orders/{plain}/subsidy")
    assert created.status_code == 201, created.text
    assert created.json()["missing_documents"] == [d.value for d in SubsidyDocType]
    _error(client.post(f"/api/v1/orders/{plain}/subsidy"), 409, "SUBSIDY_EXISTS")


def test_applied_blocked_until_documents_received(subsidy):
    client, sid = subsidy["client"], subsidy["id"]
    _tick(client, sid, "electricity_bill", "id_proof")
    error = _error(_advance(client, sid, "submitted", application_number="PM-1"), 409,
                   "DOCUMENTS_MISSING")
    assert set(error["fields"]) == {"bank_details", "roof_photos", "net_meter_application"}

    _tick(client, sid, *BEFORE_CERT)
    _error(_advance(client, sid, "submitted"), 422, "validation_error")
    number = f"PM-{sid}-{TODAY}"
    ok = _advance(client, sid, "submitted", application_number=number)
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "submitted"
    assert ok.json()["applied_on"] == TODAY
    assert ok.json()["missing_documents"] == ["installation_certificate"]


def test_inspection_needs_completed_install_and_certificate(db, subsidy):
    client, sid = subsidy["client"], subsidy["id"]
    _tick(client, sid, *BEFORE_CERT)
    assert _advance(client, sid, "submitted", application_number=f"PM-I-{sid}").status_code == 200

    _tick(client, sid, "installation_certificate")
    _error(_advance(client, sid, "under_review"), 409, "INSTALLATION_NOT_COMPLETED")

    job = db.scalars(
        select(InstallationJob).where(InstallationJob.order_id == subsidy["order_id"])
    ).one()
    job.status = InstallationJobStatus.COMPLETED
    db.commit()
    client.patch(f"/api/v1/subsidies/{sid}/documents/installation_certificate",
                 json={"received": False})
    _error(_advance(client, sid, "under_review"), 409, "DOCUMENTS_MISSING")
    _tick(client, sid, "installation_certificate")
    assert _advance(client, sid, "under_review").status_code == 200

    _error(_advance(client, sid, "approved", amount="0"), 422, "validation_error")
    sanctioned = _advance(client, sid, "approved", amount="78000.00")
    assert sanctioned.json()["sanctioned_amount"] == "78000.00"

    _error(_advance(client, sid, "paid", amount="78000.01"), 422, "validation_error")
    paid = _advance(client, sid, "paid", amount="78000.00")
    assert paid.status_code == 200, paid.text
    assert paid.json()["disbursed_amount"] == "78000.00"
    _error(_advance(client, sid, "rejected", reason="late"), 409, "INVALID_SUBSIDY_STEP")
    _error(client.patch(f"/api/v1/subsidies/{sid}/documents/id_proof",
                        json={"received": False}), 409, "SUBSIDY_CLOSED")


def test_skipping_a_step_and_rejection_reason(subsidy, api, db):
    client, sid = subsidy["client"], subsidy["id"]
    _tick(client, sid, *BEFORE_CERT)
    _error(_advance(client, sid, "under_review"), 409, "INVALID_SUBSIDY_STEP")
    _error(_advance(client, sid, "approved", amount="10"), 409, "INVALID_SUBSIDY_STEP")
    _error(_advance(client, sid, "documents_collected"), 409, "INVALID_SUBSIDY_STEP")

    _error(_advance(client, sid, "rejected"), 422, "validation_error")
    rejected = _advance(client, sid, "rejected", reason="Roof not eligible")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["rejection_reason"] == "Roof not eligible"

    listed = client.get("/api/v1/subsidies", params={"status": "rejected", "page_size": 100})
    assert listed.status_code == 200
    row = next(i for i in listed.json()["items"] if i["id"] == sid)
    assert row["missing_document_count"] == 1 and row["days_in_status"] == 0

    technician = api(_user(db, UserRole.TECHNICIAN))
    assert technician.get(f"/api/v1/subsidies/{sid}").status_code == 403


def test_document_file_upload_rules(subsidy):
    client, sid = subsidy["client"], subsidy["id"]
    url = f"/api/v1/subsidies/{sid}/documents/electricity_bill/file"
    pdf = client.post(url, files={"file": ("bill.png", b"%PDF-1.7\n" + b"x" * 100, "image/png")})
    assert pdf.status_code == 200, pdf.text
    doc = next(d for d in pdf.json()["documents"] if d["doc_type"] == "electricity_bill")
    assert doc["received"] and doc["has_file"]

    text = client.post(url, files={"file": ("bill.pdf", b"hello", "application/pdf")})
    _error(text, 422, "FILE_TYPE_NOT_ALLOWED")
    big = client.post(url, files={"file": ("b.pdf", b"%PDF" + b"0" * (5 * 1024 * 1024), "a/b")})
    _error(big, 413, "FILE_TOO_LARGE")
