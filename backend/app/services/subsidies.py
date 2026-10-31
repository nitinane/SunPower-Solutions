"""
Government rooftop subsidy paperwork, per order, until the money arrives.

Chain (spec name -> DB status, docs/decisions.md):
  DOCUMENTS_PENDING draft -> APPLIED submitted -> INSPECTED under_review
  -> SANCTIONED approved -> DISBURSED paid;  REJECTED rejected from any step before paid.
Rules enforced here:
- Advance only to the next step or to rejected (reason required), else 409 INVALID_SUBSIDY_STEP.
- -> submitted: every document except installation_certificate received (409
  DOCUMENTS_MISSING) and an application number.
- -> under_review: installation job completed and installation_certificate received.
- -> approved: amount > 0.  -> paid: 0 < amount <= sanctioned amount (422).
- Documents are a received yes/no checklist plus an optional file. No ID numbers are stored.
Every change is written to audit_log in the same transaction.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.dates import ist_date, today_ist
from app.core.enums import InstallationJobStatus, SubsidyDocType, SubsidyStatus
from app.exceptions import BusinessRuleViolation, NotFound, ValidationFailed
from app.models.orders import Order
from app.models.subsidies import SubsidyApplication
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import orders as order_repo
from app.repositories import subsidies as repo
from app.schemas.subsidies import (
    SubsidyAdvance,
    SubsidyDocumentRead,
    SubsidyListItem,
    SubsidyRead,
)
from app.services.catalog import money
from app.services.common import RequestMeta
from app.services.installations import FileTooLarge, FileTypeNotAllowed, sniff_image
from app.storage import file_storage

MAX_PAGE_SIZE = 100
MAX_FILE_BYTES = 5 * 1024 * 1024  # same as installation photos
PDF_MAGIC = b"%PDF"
SCHEME_NAME = "Rooftop solar subsidy"
CHAIN = [
    SubsidyStatus.DRAFT,          # DOCUMENTS_PENDING
    SubsidyStatus.SUBMITTED,      # APPLIED
    SubsidyStatus.UNDER_REVIEW,   # INSPECTED
    SubsidyStatus.APPROVED,       # SANCTIONED
    SubsidyStatus.PAID,           # DISBURSED
]
CLOSED = frozenset({SubsidyStatus.PAID, SubsidyStatus.REJECTED})
NEEDED_TO_APPLY = [d for d in SubsidyDocType if d != SubsidyDocType.INSTALLATION_CERTIFICATE]


class InvalidSubsidyStep(BusinessRuleViolation):
    code = "INVALID_SUBSIDY_STEP"


class DocumentsMissing(BusinessRuleViolation):
    code = "DOCUMENTS_MISSING"


class InstallationNotCompleted(BusinessRuleViolation):
    code = "INSTALLATION_NOT_COMPLETED"


class SubsidyExists(BusinessRuleViolation):
    code = "SUBSIDY_EXISTS"


class SubsidyClosed(BusinessRuleViolation):
    code = "SUBSIDY_CLOSED"


class ApplicationNumberTaken(BusinessRuleViolation):
    code = "APPLICATION_NUMBER_TAKEN"


# ---------------------------------------------------------------- Read side

def status_since(app: SubsidyApplication) -> date:
    by_status = {
        SubsidyStatus.SUBMITTED: app.applied_on,
        SubsidyStatus.UNDER_REVIEW: app.inspected_on,
        SubsidyStatus.APPROVED: app.sanctioned_on,
        SubsidyStatus.PAID: app.disbursed_on,
        SubsidyStatus.REJECTED: ist_date(app.updated_at),
    }
    return by_status.get(app.status) or ist_date(app.created_at)


def days_in_status(app: SubsidyApplication) -> int:
    return max((today_ist() - status_since(app)).days, 0)


def list_subsidies(
    db: Session, *, status: SubsidyStatus | None, page: int, page_size: int
) -> tuple[list[SubsidyListItem], int]:
    page_size = min(page_size, MAX_PAGE_SIZE)
    rows, total = repo.list_page(
        db, status=status, limit=page_size, offset=(page - 1) * page_size
    )
    items = [
        SubsidyListItem(
            id=app.id,
            order_id=app.order_id,
            order_number=order_number,
            customer_name=customer_name,
            status=app.status,
            application_number=app.application_number,
            missing_document_count=missing,
            days_in_status=days_in_status(app),
        )
        for app, order_number, customer_name, missing in rows
    ]
    return items, total


def get_subsidy(db: Session, application_id: int) -> SubsidyRead:
    app = repo.get(db, application_id)
    if app is None:
        raise NotFound("Subsidy application not found")
    return to_read(db, app)


def to_read(db: Session, app: SubsidyApplication) -> SubsidyRead:
    docs = repo.list_documents(db, app.id)
    names = repo.order_and_customer(db, app.order_id) if app.order_id else None
    customer_name = names[1] if names else ""
    return SubsidyRead(
        id=app.id,
        order_id=app.order_id,
        order_number=names[0] if names else None,
        customer_name=customer_name,
        status=app.status,
        application_number=app.application_number,
        applied_on=app.applied_on,
        inspected_on=app.inspected_on,
        sanctioned_amount=app.approved_amount,
        sanctioned_on=app.sanctioned_on,
        disbursed_amount=app.disbursed_amount,
        disbursed_on=app.disbursed_on,
        rejection_reason=app.rejection_reason,
        notes=app.notes,
        documents=[
            SubsidyDocumentRead(
                doc_type=d.doc_type, received=d.received, received_on=d.received_on,
                has_file=d.storage_key is not None,
            )
            for d in docs
        ],
        missing_documents=[d.doc_type for d in docs if not d.received],
        days_in_status=days_in_status(app),
        created_at=app.created_at,
    )


# ---------------------------------------------------------------- Create

def create_for_order(
    db: Session, order: Order, *, actor: User, meta: RequestMeta | None = None
) -> SubsidyApplication:
    """Insert the application (draft) with all 6 document rows. Caller holds the order lock
    and commits."""
    app = repo.create(
        db,
        {
            "customer_id": order.customer_id,
            "site_id": order.site_id,
            "order_id": order.id,
            "scheme_name": SCHEME_NAME,
            "status": SubsidyStatus.DRAFT,
        },
        [d.value for d in SubsidyDocType],
    )
    _audit(db, actor, "subsidy.created", app.id, None, snapshot(app), meta)
    return app


def create_on_first_payment(
    db: Session, order: Order, *, actor: User, meta: RequestMeta | None = None
) -> None:
    """Called inside record_payment when the first payment confirms the order."""
    if repo.subsidy_requested(db, order.id) and repo.get_by_order(db, order.id) is None:
        create_for_order(db, order, actor=actor, meta=meta)


def create_manually(
    db: Session, order_id: int, *, actor: User, meta: RequestMeta | None = None
) -> SubsidyApplication:
    order = order_repo.get_by_id_for_update(db, order_id)
    if order is None:
        raise NotFound("Order not found")
    if repo.get_by_order(db, order.id) is not None:
        raise SubsidyExists("This order already has a subsidy application")
    app = create_for_order(db, order, actor=actor, meta=meta)
    db.commit()
    db.refresh(app)
    return app


# ---------------------------------------------------------------- Documents

def set_document(
    db: Session,
    application_id: int,
    doc_type: SubsidyDocType,
    received: bool,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> SubsidyApplication:
    app = _get_open_for_update(db, application_id)
    doc = repo.get_document(db, app.id, doc_type, lock=True)
    old = {"doc_type": doc.doc_type, "received": doc.received}
    repo.update(db, doc, {"received": received, "received_on": today_ist() if received else None})
    _audit(db, actor, "subsidy.document_updated", app.id, old,
           {"doc_type": doc.doc_type, "received": received}, meta)
    db.commit()
    db.refresh(app)
    return app


def upload_document(
    db: Session,
    application_id: int,
    doc_type: SubsidyDocType,
    content: bytes,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> SubsidyApplication:
    app = _get_open_for_update(db, application_id)
    if len(content) > MAX_FILE_BYTES:
        raise FileTooLarge("File is larger than 5 MB", fields={"file": "Max 5 MB"})
    detected = sniff_file(content)
    if detected is None:
        raise FileTypeNotAllowed(
            "Only JPEG, PNG, WEBP or PDF files are allowed",
            fields={"file": "Not a JPEG/PNG/WEBP/PDF"},
        )
    content_type, ext = detected
    doc = repo.get_document(db, app.id, doc_type, lock=True)
    key = file_storage.save_bytes(content, ext)
    repo.update(
        db,
        doc,
        {
            "storage_key": key,
            "content_type": content_type,
            "received": True,
            "received_on": doc.received_on or today_ist(),
        },
    )
    _audit(db, actor, "subsidy.document_uploaded", app.id, None,
           {"doc_type": doc.doc_type, "size_bytes": len(content)}, meta)
    db.commit()
    db.refresh(app)
    return app


def sniff_file(content: bytes) -> tuple[str, str] | None:
    if content.startswith(PDF_MAGIC):
        return "application/pdf", "pdf"
    return sniff_image(content)


# ---------------------------------------------------------------- Advance

def advance(
    db: Session,
    application_id: int,
    data: SubsidyAdvance,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> SubsidyApplication:
    app = repo.get(db, application_id, lock=True)
    if app is None:
        raise NotFound("Subsidy application not found")
    if data.date > today_ist():
        raise ValidationFailed("Date cannot be in the future", fields={"date": "Not after today"})

    target = data.to_status
    if target == SubsidyStatus.REJECTED:
        if app.status in CLOSED:
            raise InvalidSubsidyStep(f"A {app.status} application cannot be rejected")
        if not data.reason:
            raise ValidationFailed("A reason is required", fields={"reason": "Required"})
        changes: dict[str, Any] = {"status": target, "rejection_reason": data.reason}
    else:
        current = CHAIN.index(app.status) if app.status in CHAIN else None
        if current is None or current + 1 >= len(CHAIN) or CHAIN[current + 1] != target:
            raise InvalidSubsidyStep(
                f"Cannot move a subsidy from {app.status} to {target}"
            )
        changes = _step_changes(db, app, data)

    old = snapshot(app)
    repo.update(db, app, changes)
    _audit(db, actor, f"subsidy.{target}", app.id, old,
           {**snapshot(app), "date": data.date.isoformat()}, meta)
    db.commit()
    db.refresh(app)
    return app


def _step_changes(db: Session, app: SubsidyApplication, data: SubsidyAdvance) -> dict[str, Any]:
    target = data.to_status
    if target == SubsidyStatus.SUBMITTED:
        _require_documents(db, app, NEEDED_TO_APPLY)
        if not data.application_number:
            raise ValidationFailed(
                "Application number is required", fields={"application_number": "Required"}
            )
        other = repo.get_by_application_number(db, data.application_number)
        if other is not None and other.id != app.id:
            raise ApplicationNumberTaken("This application number is already used")
        return {"status": target, "application_number": data.application_number,
                "applied_on": data.date}

    if target == SubsidyStatus.UNDER_REVIEW:
        job = order_repo.get_installation_job(db, app.order_id) if app.order_id else None
        if job is None or job.status != InstallationJobStatus.COMPLETED:
            raise InstallationNotCompleted("The installation must be completed before inspection")
        _require_documents(db, app, [SubsidyDocType.INSTALLATION_CERTIFICATE])
        return {"status": target, "inspected_on": data.date}

    if target == SubsidyStatus.APPROVED:
        if data.amount is None or data.amount <= 0:
            raise ValidationFailed("Sanctioned amount must be more than 0",
                                   fields={"amount": "Must be > 0"})
        return {"status": target, "approved_amount": money(data.amount),
                "sanctioned_on": data.date}

    # SubsidyStatus.PAID
    sanctioned = app.approved_amount or Decimal("0")
    if data.amount is None or not Decimal("0") < data.amount <= sanctioned:
        raise ValidationFailed(
            f"Disbursed amount must be more than 0 and at most ₹{sanctioned}",
            fields={"amount": f"0 < amount <= {sanctioned}"},
        )
    return {"status": target, "disbursed_amount": money(data.amount), "disbursed_on": data.date}


def _require_documents(db: Session, app: SubsidyApplication, needed: list[str]) -> None:
    received = {d.doc_type for d in repo.list_documents(db, app.id) if d.received}
    missing = [d for d in needed if d not in received]
    if missing:
        raise DocumentsMissing(
            "Documents missing: " + ", ".join(missing),
            fields={d: "Not received" for d in missing},
        )


# ---------------------------------------------------------------- Internal helpers

def _get_open_for_update(db: Session, application_id: int) -> SubsidyApplication:
    app = repo.get(db, application_id, lock=True)
    if app is None:
        raise NotFound("Subsidy application not found")
    if app.status in CLOSED:
        raise SubsidyClosed(f"This application is {app.status}; documents can no longer change")
    return app


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def snapshot(app: SubsidyApplication) -> dict[str, Any]:
    fields = ("status", "order_id", "application_number", "applied_on", "inspected_on",
              "approved_amount", "sanctioned_on", "disbursed_amount", "disbursed_on",
              "rejection_reason")
    return {field: _json_safe(getattr(app, field)) for field in fields}


def _audit(
    db: Session,
    actor: User,
    action: str,
    entity_id: int,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
    meta: RequestMeta | None,
) -> None:
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id,
        action=action,
        entity_type="subsidy_application",
        entity_id=entity_id,
        old_data=old,
        new_data=new,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )
