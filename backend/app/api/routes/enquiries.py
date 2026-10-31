


"""
Feature 1 HTTP layer: enquiry inbox + qualification call.

Only HTTP work happens here: read the request, check the role, call the service, shape the
response. All rules live in app/services/enquiries.py. Handlers are plain `def` (not async)
because SQLAlchemy is synchronous; FastAPI runs them in a thread pool so they never block.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.enums import EnquirySource, EnquiryStatus, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.enquiries import (
    EnquiryAssign,
    EnquiryClose,
    EnquiryPublicCreate,
    EnquiryPublicReceipt,
    EnquiryQualify,
    EnquiryRead,
    EnquiryStaffCreate,
)
from app.services import enquiries as enquiry_service
from app.services.enquiries import RequestMeta

router = APIRouter(prefix="/enquiries", tags=["enquiries"])

STAFF_ROLES = (UserRole.OFFICE, UserRole.DIRECTOR, UserRole.ADMIN)
require_staff = require_role(*STAFF_ROLES)

DbSession = Annotated[Session, Depends(get_db)]
StaffUser = Annotated[User, Depends(require_staff)]
EnquiryId = Annotated[int, Path(gt=0, description="Enquiry id")]
IdempotencyKey = Annotated[
    str | None,
    Header(max_length=100, description="Same key = same result (safe retries)"),
]


def _meta(request: Request) -> RequestMeta:
    """Request ID + client IP for the audit log."""
    return RequestMeta(
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
    )


# ---------------------------------------------------------------- Public (no login)

@router.post(
    "/public",
    response_model=EnquiryPublicReceipt,
    status_code=status.HTTP_201_CREATED,
    summary="Website enquiry form (no login)",
)
def submit_public_enquiry(
    data: EnquiryPublicCreate,
    request: Request,
    response: Response,
    db: DbSession,
    idempotency_key: IdempotencyKey = None,
) -> EnquiryPublicReceipt:
    enquiry, created = enquiry_service.create_public_enquiry(
        db, data, idempotency_key=idempotency_key, meta=_meta(request)
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return EnquiryPublicReceipt(
        reference=enquiry_service.public_reference(enquiry),
        message="Thank you! Our sales team will call you shortly.",
    )


# ---------------------------------------------------------------- Staff

@router.post(
    "",
    response_model=EnquiryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Log a phone / WhatsApp / walk-in / referral enquiry",
)
def log_enquiry(
    data: EnquiryStaffCreate,
    request: Request,
    db: DbSession,
    actor: StaffUser,
    idempotency_key: IdempotencyKey = None,
) -> EnquiryRead:
    enquiry = enquiry_service.create_staff_enquiry(
        db, data, actor=actor, idempotency_key=idempotency_key, meta=_meta(request)
    )
    return enquiry_service.to_read(enquiry)


@router.get("", response_model=Page[EnquiryRead], summary="Sales inbox")
def list_enquiries(
    db: DbSession,
    actor: StaffUser,
    status_filter: Annotated[EnquiryStatus | None, Query(alias="status")] = None,
    source: EnquirySource | None = None,
    assigned: Annotated[
        str | None,
        Query(pattern=r"^(me|unassigned|[1-9][0-9]*)$", description="me | unassigned | user id"),
    ] = None,
    overdue: bool = False,
    search: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[EnquiryRead]:
    items, total = enquiry_service.list_enquiries(
        db,
        actor=actor,
        status=status_filter,
        source=source,
        assigned=assigned,
        overdue=overdue,
        search=search,
        page=page,
        page_size=page_size,
    )
    now = datetime.now(UTC)
    return Page[EnquiryRead](
        items=[enquiry_service.to_read(item, now) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{enquiry_id}", response_model=EnquiryRead, summary="One enquiry")
def get_enquiry(enquiry_id: EnquiryId, db: DbSession, actor: StaffUser) -> EnquiryRead:
    return enquiry_service.to_read(enquiry_service.get_enquiry(db, enquiry_id))


@router.post("/{enquiry_id}/assign", response_model=EnquiryRead, summary="Assign to a salesperson")
def assign_enquiry(
    enquiry_id: EnquiryId,
    data: EnquiryAssign,
    request: Request,
    db: DbSession,
    actor: StaffUser,
) -> EnquiryRead:
    enquiry = enquiry_service.assign_enquiry(
        db, enquiry_id, data, actor=actor, meta=_meta(request)
    )
    return enquiry_service.to_read(enquiry)


@router.post(
    "/{enquiry_id}/qualification",
    response_model=EnquiryRead,
    summary="Save the qualification call sheet",
)
def record_qualification(
    enquiry_id: EnquiryId,
    data: EnquiryQualify,
    request: Request,
    db: DbSession,
    actor: StaffUser,
) -> EnquiryRead:
    enquiry = enquiry_service.record_qualification(
        db, enquiry_id, data, actor=actor, meta=_meta(request)
    )
    return enquiry_service.to_read(enquiry)


@router.post("/{enquiry_id}/close", response_model=EnquiryRead, summary="Close with a reason")
def close_enquiry(
    enquiry_id: EnquiryId,
    data: EnquiryClose,
    request: Request,
    db: DbSession,
    actor: StaffUser,
) -> EnquiryRead:
    enquiry = enquiry_service.close_enquiry(
        db, enquiry_id, data, actor=actor, meta=_meta(request)
    )
    return enquiry_service.to_read(enquiry)