"""Enquiries service stub. TODO: implement with the owning team."""
"""
Feature 1: Enquiry inbox + qualification call.

PDF scene "The rooftop inquiry": a web, phone or WhatsApp enquiry lands with sales straight
away and never vanishes. Someone calls to check shadow-free roof space, monthly bill and grid
suitability. Only then does a technician survey follow.

Rules enforced here (never only in the UI):
- No delete exists. Closing needs a reason. Every change is written to audit_log.
- Same phone with an open enquiry -> no duplicate
  (web form: reuse it; staff: 409 with its reference).
- Same Idempotency-Key -> the first result is returned (safe retries and double clicks).
- Qualifying needs a suitable grid connection, then links-or-creates the customer (by phone)
  and the site, all in ONE transaction.

Transactions: this module commits. Repositories only add/flush. If anything raises before the
commit, the request's session is closed and nothing is saved.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import EnquirySource, EnquiryStatus, UserRole
from app.core.validators import normalize_phone
from app.exceptions import BusinessRuleViolation, Conflict, NotFound, ValidationFailed
from app.models.customers import Customer, Site
from app.models.enquiries import Enquiry
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import customers as customer_repo
from app.repositories import enquiries as enquiry_repo
from app.repositories import users as user_repo
from app.schemas.enquiries import (
    EnquiryAssign,
    EnquiryClose,
    EnquiryPublicCreate,
    EnquiryQualify,
    EnquiryRead,
    EnquiryStaffCreate,
)

OVERDUE_AFTER = timedelta(hours=24)
MAX_PAGE_SIZE = 100

OPEN_STATUSES = frozenset({EnquiryStatus.NEW, EnquiryStatus.CONTACTED, EnquiryStatus.QUALIFIED})
QUALIFIABLE_FROM = frozenset({EnquiryStatus.NEW, EnquiryStatus.CONTACTED})
QUALIFICATION_OUTCOMES = frozenset(
    {EnquiryStatus.CONTACTED, EnquiryStatus.QUALIFIED, EnquiryStatus.UNQUALIFIED}
)
ASSIGNEE_ROLES = frozenset({UserRole.OFFICE, UserRole.DIRECTOR, UserRole.ADMIN})

AUDIT_FIELDS = (
    "status",
    "source",
    "assigned_to",
    "customer_id",
    "site_id",
    "shadow_free_roof_area_sqft",
    "monthly_bill_amount",
    "grid_connection_suitable",
    "qualified_by",
    "qualified_at",
    "close_reason",
)


@dataclass(frozen=True)
class RequestMeta:
    """Where a request came from; saved in audit_log next to each change."""

    request_id: str | None = None
    ip_address: str | None = None


# ---------------------------------------------------------------- Read side

def public_reference(enquiry: Enquiry) -> str:
    """Human-friendly reference shown to the customer, e.g. ENQ-000123."""
    return f"ENQ-{enquiry.id:06d}"


def is_overdue(enquiry: Enquiry, now: datetime | None = None) -> bool:
    """True when nobody has touched a new enquiry for 24 hours."""
    now = now or _now()
    return enquiry.status == EnquiryStatus.NEW and enquiry.created_at <= now - OVERDUE_AFTER


def to_read(enquiry: Enquiry, now: datetime | None = None) -> EnquiryRead:
    """ORM row -> API response, with is_overdue filled in by the business rule above."""
    read = EnquiryRead.model_validate(enquiry)
    return read.model_copy(update={"is_overdue": is_overdue(enquiry, now)})


def get_enquiry(db: Session, enquiry_id: int) -> Enquiry:
    """Fetch one enquiry or raise 404."""
    enquiry = enquiry_repo.get_by_id(db, enquiry_id)
    if enquiry is None:
        raise NotFound("Enquiry not found")
    return enquiry


def list_enquiries(
    db: Session,
    *,
    actor: User,
    status: EnquiryStatus | None = None,
    source: EnquirySource | None = None,
    assigned: str | None = None,
    overdue: bool = False,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Enquiry], int]:
    """Sales inbox.

    assigned = 'me' | 'unassigned' | '<user id>'; overdue = new and older than 24 h.
    """
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    assigned_to: int | None = None
    unassigned = False
    if assigned == "me":
        assigned_to = actor.id
    elif assigned == "unassigned":
        unassigned = True
    elif assigned:
        try:
            assigned_to = int(assigned)
        except ValueError:
            raise ValidationFailed(
                "Invalid assigned filter",
                fields={"assigned": "Use 'me', 'unassigned' or a user id"},
            ) from None

    created_before: datetime | None = None
    if overdue:
        status = EnquiryStatus.NEW
        created_before = _now() - OVERDUE_AFTER

    return enquiry_repo.list_page(
        db,
        status=status,
        source=source,
        assigned_to=assigned_to,
        unassigned=unassigned,
        created_before=created_before,
        search=(search or "").strip() or None,
        limit=page_size,
        offset=(page - 1) * page_size,
    )


# ---------------------------------------------------------------- Create

def create_public_enquiry(
    db: Session,
    data: EnquiryPublicCreate,
    *,
    idempotency_key: str | None = None,
    meta: RequestMeta | None = None,
) -> tuple[Enquiry, bool]:
    """Website form. Returns (enquiry, created). Repeat submissions reuse the open enquiry."""
    if data.website_url:
        raise ValidationFailed("Submission rejected")  # honeypot filled -> a bot

    if idempotency_key:
        existing = enquiry_repo.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing, False

    values = _contact_fields(data)
    open_enquiry = enquiry_repo.find_open_by_phone(db, values["phone_e164"])
    if open_enquiry is not None:
        _record_repeat_submission(db, open_enquiry, data.notes, meta)
        return open_enquiry, False

    values.update(source=EnquirySource.WEBSITE, status=EnquiryStatus.NEW)
    return _insert_enquiry(db, values, actor=None, idempotency_key=idempotency_key, meta=meta)


def create_staff_enquiry(
    db: Session,
    data: EnquiryStaffCreate,
    *,
    actor: User,
    idempotency_key: str | None = None,
    meta: RequestMeta | None = None,
) -> Enquiry:
    """Staff logs a phone / WhatsApp / walk-in / referral enquiry."""
    if data.source == EnquirySource.WEBSITE:
        raise ValidationFailed(
            "Website enquiries come only from the public form",
            fields={"source": "Choose phone, WhatsApp, walk-in, referral or other"},
        )

    if idempotency_key:
        existing = enquiry_repo.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing

    values = _contact_fields(data)
    open_enquiry = enquiry_repo.find_open_by_phone(db, values["phone_e164"])
    if open_enquiry is not None:
        raise Conflict(
            f"An open enquiry {public_reference(open_enquiry)} already exists for this phone number"
        )

    values.update(
        source=data.source,
        status=EnquiryStatus.NEW,
        assigned_to=actor.id if actor.role == UserRole.OFFICE else None,
    )
    enquiry, _ = _insert_enquiry(
        db, values, actor=actor, idempotency_key=idempotency_key, meta=meta
    )
    return enquiry


# ---------------------------------------------------------------- Workflow actions

def assign_enquiry(
    db: Session,
    enquiry_id: int,
    data: EnquiryAssign,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> Enquiry:
    """Give an open enquiry to an active office user."""
    enquiry = _get_for_update(db, enquiry_id)
    _require_status(enquiry, OPEN_STATUSES, "Only open enquiries can be assigned")

    assignee = user_repo.get_by_id(db, data.user_id)
    if assignee is None or not assignee.is_active or assignee.role not in ASSIGNEE_ROLES:
        raise ValidationFailed(
            "Cannot assign to this user",
            fields={"user_id": "Choose an active office user"},
        )

    old = _snapshot(enquiry)
    enquiry_repo.update(db, enquiry, {"assigned_to": assignee.id})
    _audit(db, actor, "enquiry.assigned", enquiry, old, _snapshot(enquiry), meta)
    db.commit()
    db.refresh(enquiry)
    return enquiry


def record_qualification(
    db: Session,
    enquiry_id: int,
    data: EnquiryQualify,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> Enquiry:
    """Save the qualification call sheet.

    Outcome: contacted (follow-up needed), qualified or unqualified.
    """
    enquiry = _get_for_update(db, enquiry_id)
    _require_status(enquiry, QUALIFIABLE_FROM, "Only new or contacted enquiries can be qualified")

    outcome = EnquiryStatus(data.outcome)
    if outcome not in QUALIFICATION_OUTCOMES:
        raise ValidationFailed(
            "Invalid call outcome",
            fields={"outcome": "Choose contacted, qualified or unqualified"},
        )

    now = _now()
    old = _snapshot(enquiry)
    changes: dict[str, Any] = {
        "shadow_free_roof_area_sqft": data.shadow_free_roof_area_sqft,
        "monthly_bill_amount": data.monthly_bill_amount,
        "grid_connection_suitable": data.grid_connection_suitable,
        "status": outcome,
    }
    if data.notes:
        changes["notes"] = _append_note(
            enquiry.notes, f"call by {actor.full_name}", data.notes, now
        )
    if enquiry.assigned_to is None:
        changes["assigned_to"] = actor.id

    if outcome == EnquiryStatus.QUALIFIED:
        if not data.grid_connection_suitable:
            raise BusinessRuleViolation(
                "Grid connection must be suitable before the enquiry can be qualified",
                fields={"grid_connection_suitable": "Must be yes to qualify"},
            )
        customer, site = _link_customer_and_site(db, enquiry, actor)
        changes.update(
            customer_id=customer.id,
            site_id=site.id,
            qualified_by=actor.id,
            qualified_at=now,
        )

    enquiry_repo.update(db, enquiry, changes)
    _audit(db, actor, f"enquiry.call_{outcome}", enquiry, old, _snapshot(enquiry), meta)
    db.commit()
    db.refresh(enquiry)
    return enquiry


def close_enquiry(
    db: Session,
    enquiry_id: int,
    data: EnquiryClose,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> Enquiry:
    """Close an open enquiry with a reason. It stays in the database forever."""
    enquiry = _get_for_update(db, enquiry_id)
    _require_status(enquiry, OPEN_STATUSES, "This enquiry is already finished")

    old = _snapshot(enquiry)
    enquiry_repo.update(db, enquiry, {"status": EnquiryStatus.CLOSED, "close_reason": data.reason})
    _audit(db, actor, "enquiry.closed", enquiry, old, _snapshot(enquiry), meta)
    db.commit()
    db.refresh(enquiry)
    return enquiry


# ---------------------------------------------------------------- Internal helpers

def _now() -> datetime:
    return datetime.now(UTC)


def _get_for_update(db: Session, enquiry_id: int) -> Enquiry:
    """Lock the row (SELECT ... FOR UPDATE) so two people can't change it at the same time."""
    enquiry = enquiry_repo.get_by_id_for_update(db, enquiry_id)
    if enquiry is None:
        raise NotFound("Enquiry not found")
    return enquiry


def _require_status(enquiry: Enquiry, allowed: frozenset[EnquiryStatus], message: str) -> None:
    if enquiry.status not in allowed:
        raise BusinessRuleViolation(f"{message} (current status: {enquiry.status})")


def _contact_fields(data: EnquiryPublicCreate | EnquiryStaffCreate) -> dict[str, Any]:
    """Map form fields to enquiry columns; phone is stored both as typed and as E.164."""
    return {
        "contact_name": data.contact_name,
        "phone_raw": data.phone,
        "phone_e164": normalize_phone(data.phone),
        "email": data.email,
        "address_line": data.address_line,
        "city": data.city,
        "state": data.state,
        "pincode": data.pincode,
        "customer_type": data.customer_type,
        "system_type": data.system_type,
        "requested_capacity_kw": data.requested_capacity_kw,
        "subsidy_requested": data.subsidy_requested,
        "notes": data.notes,
    }


def _insert_enquiry(
    db: Session,
    values: dict[str, Any],
    *,
    actor: User | None,
    idempotency_key: str | None,
    meta: RequestMeta | None,
) -> tuple[Enquiry, bool]:
    """Insert + audit + commit. If a parallel request with the same key won, return that one."""
    try:
        enquiry = enquiry_repo.create(db, {**values, "idempotency_key": idempotency_key})
        _audit(db, actor, "enquiry.created", enquiry, None, _snapshot(enquiry), meta)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            enquiry_repo.get_by_idempotency_key(db, idempotency_key) if idempotency_key else None
        )
        if existing is None:
            raise Conflict(
                "This enquiry clashes with existing data. Please refresh and try again."
            ) from None
        return existing, False
    db.refresh(enquiry)
    return enquiry, True


def _record_repeat_submission(
    db: Session, enquiry: Enquiry, notes: str | None, meta: RequestMeta | None
) -> None:
    """Customer submitted the web form again: keep their new message, log it, no duplicate row."""
    if notes:
        note = _append_note(enquiry.notes, "customer, repeat web form", notes, _now())
        enquiry_repo.update(db, enquiry, {"notes": note})
    _audit(db, None, "enquiry.repeat_submission", enquiry, None, {"notes": notes}, meta)
    db.commit()


def _link_customer_and_site(db: Session, enquiry: Enquiry, actor: User) -> tuple[Customer, Site]:
    """Reuse the customer with this phone (or create one), then reuse or create the roof site."""
    if not enquiry.phone_e164:
        raise BusinessRuleViolation("This enquiry has no valid phone number")

    customer = customer_repo.get_by_phone(db, enquiry.phone_e164)
    if customer is None:
        customer = customer_repo.create(
            db,
            {
                "full_name": enquiry.contact_name,
                "phone_e164": enquiry.phone_e164,
                "email": enquiry.email,
                "created_by": actor.id,
            },
        )

    site = customer_repo.find_site(db, customer.id, enquiry.address_line, enquiry.pincode)
    if site is None:
        site = customer_repo.create_site(
            db,
            {
                "customer_id": customer.id,
                "address_line1": enquiry.address_line,
                "city": enquiry.city,
                "state": enquiry.state,
                "pincode": enquiry.pincode,
            },
        )
    return customer, site


def _append_note(existing: str | None, author: str, text: str, now: datetime) -> str:
    """Add a dated line to the notes instead of overwriting them."""
    entry = f"[{now:%d %b %Y %H:%M} UTC - {author}] {text}"
    return f"{existing}\n{entry}" if existing else entry


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _snapshot(enquiry: Enquiry) -> dict[str, Any]:
    """The fields we record in audit_log before/after each change."""
    return {field: _json_safe(getattr(enquiry, field, None)) for field in AUDIT_FIELDS}


def _audit(
    db: Session,
    actor: User | None,
    action: str,
    enquiry: Enquiry,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
    meta: RequestMeta | None,
) -> None:
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id if actor else None,
        action=action,
        entity_type="enquiry",
        entity_id=enquiry.id,
        old_data=old,
        new_data=new,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )