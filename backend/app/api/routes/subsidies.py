"""
Government subsidy paperwork per order: document checklist, files and status steps.
All rules live in app/services/subsidies.py.
"""

from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import SubsidyDocType, SubsidyStatus, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.subsidies import DocumentUpdate, SubsidyAdvance, SubsidyListItem, SubsidyRead
from app.services import subsidies as subsidy_service
from app.services.common import RequestMeta

router = APIRouter(tags=["subsidies"])

DbSession = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Office = Annotated[User, Depends(require_role(UserRole.OFFICE, UserRole.DIRECTOR))]
SubsidyId = Annotated[int, Path(gt=0)]
# Read one byte past the service limit so the service can tell "too large" apart.
UPLOAD_READ_LIMIT = subsidy_service.MAX_FILE_BYTES + 1


@router.get("/subsidies", response_model=Page[SubsidyListItem], summary="Subsidy tracker")
def list_subsidies(
    db: DbSession,
    actor: Office,
    status_filter: Annotated[SubsidyStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[SubsidyListItem]:
    items, total = subsidy_service.list_subsidies(
        db, status=status_filter, page=page, page_size=page_size
    )
    return Page[SubsidyListItem](items=items, total=total, page=page, page_size=page_size)


@router.get("/subsidies/{subsidy_id}", response_model=SubsidyRead, summary="Subsidy detail")
def get_subsidy(subsidy_id: SubsidyId, db: DbSession, actor: Office) -> SubsidyRead:
    return subsidy_service.get_subsidy(db, subsidy_id)


@router.post(
    "/orders/{order_id}/subsidy",
    response_model=SubsidyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start a subsidy application for an order",
)
def create_subsidy(
    order_id: Annotated[int, Path(gt=0)], db: DbSession, actor: Office, meta: Meta
) -> SubsidyRead:
    app = subsidy_service.create_manually(db, order_id, actor=actor, meta=meta)
    return subsidy_service.to_read(db, app)


@router.patch(
    "/subsidies/{subsidy_id}/documents/{doc_type}",
    response_model=SubsidyRead,
    summary="Tick a document as received (or not)",
)
def set_document(
    subsidy_id: SubsidyId,
    doc_type: SubsidyDocType,
    data: DocumentUpdate,
    db: DbSession,
    actor: Office,
    meta: Meta,
) -> SubsidyRead:
    app = subsidy_service.set_document(
        db, subsidy_id, doc_type, data.received, actor=actor, meta=meta
    )
    return subsidy_service.to_read(db, app)


@router.post(
    "/subsidies/{subsidy_id}/documents/{doc_type}/file",
    response_model=SubsidyRead,
    summary="Upload a document file (JPEG/PNG/WEBP/PDF, max 5 MB)",
)
def upload_document(
    subsidy_id: SubsidyId,
    doc_type: SubsidyDocType,
    db: DbSession,
    actor: Office,
    meta: Meta,
    file: Annotated[UploadFile, File()],
) -> SubsidyRead:
    content = file.file.read(UPLOAD_READ_LIMIT)
    app = subsidy_service.upload_document(
        db, subsidy_id, doc_type, content, actor=actor, meta=meta
    )
    return subsidy_service.to_read(db, app)


@router.post(
    "/subsidies/{subsidy_id}/advance",
    response_model=SubsidyRead,
    summary="Move to the next subsidy step, or reject",
)
def advance(
    subsidy_id: SubsidyId, data: SubsidyAdvance, db: DbSession, actor: Office, meta: Meta
) -> SubsidyRead:
    app = subsidy_service.advance(db, subsidy_id, data, actor=actor, meta=meta)
    return subsidy_service.to_read(db, app)


@router.get("/subsidies/{subsidy_id}/documents/{doc_type}/file",
            response_class=StreamingResponse,
            responses={200: {"content": {"application/octet-stream": {}}}})
def download_document(
    subsidy_id: SubsidyId, doc_type: SubsidyDocType, db: DbSession, actor: Office,
) -> StreamingResponse:
    content, content_type = subsidy_service.download_document(db, subsidy_id, doc_type)
    return StreamingResponse(BytesIO(content), media_type=content_type)
