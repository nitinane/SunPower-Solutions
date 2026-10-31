"""
Crew schedule + installation-day phone form + evidence files.

Managers book a date and crew; the crew technician starts the job, adds photos and completes
it with the customer's signature. All rules live in app/services/installations.py and
app/services/schedule.py.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, get_request_meta, require_role
from app.core.enums import InstallationJobStatus, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.installations import (
    EvidenceRead,
    JobComplete,
    JobRead,
    ScheduleCreate,
    ScheduleRow,
)
from app.services import installations as job_service
from app.services import schedule as schedule_service
from app.services.common import RequestMeta

router = APIRouter(tags=["installations"])

DbSession = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Planner = Annotated[User, Depends(require_role(UserRole.MANAGER, UserRole.DIRECTOR))]
ScheduleViewer = Annotated[
    User, Depends(require_role(UserRole.MANAGER, UserRole.OFFICE, UserRole.DIRECTOR))
]
JobViewer = Annotated[
    User,
    Depends(
        require_role(UserRole.TECHNICIAN, UserRole.MANAGER, UserRole.OFFICE, UserRole.DIRECTOR)
    ),
]
Technician = Annotated[User, Depends(require_role(UserRole.TECHNICIAN))]
Staff = Annotated[User, Depends(get_current_user)]
JobId = Annotated[int, Path(gt=0)]
# Read one byte past the service limit so the service can tell "too large" apart.
UPLOAD_READ_LIMIT = job_service.MAX_PHOTO_BYTES + 1


@router.get("/schedule", response_model=Page[ScheduleRow], summary="Crew calendar")
def get_schedule(
    db: DbSession,
    actor: ScheduleViewer,
    first: Annotated[date, Query(alias="from")],
    last: Annotated[date, Query(alias="to")],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[ScheduleRow]:
    items, total = schedule_service.list_schedule(
        db, first=first, last=last, page=page, page_size=page_size
    )
    return Page[ScheduleRow](items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/installation-jobs/{job_id}/schedule",
    response_model=JobRead,
    summary="Book a date and crew (no double booking)",
)
def schedule_job(
    job_id: JobId, data: ScheduleCreate, db: DbSession, actor: Planner, meta: Meta
) -> JobRead:
    job = schedule_service.schedule_job(db, job_id, data, actor=actor, meta=meta)
    return job_service.get_job_read(db, job.id, actor=actor)


@router.get("/installation-jobs/{job_id}", response_model=JobRead, summary="Job sheet")
def get_job(job_id: JobId, db: DbSession, actor: JobViewer) -> JobRead:
    return job_service.get_job_read(db, job_id, actor=actor)


@router.post(
    "/installation-jobs/{job_id}/start", response_model=JobRead, summary="SCHEDULED -> IN_PROGRESS"
)
def start_job(job_id: JobId, db: DbSession, actor: Technician, meta: Meta) -> JobRead:
    job = job_service.start_job(db, job_id, actor=actor, meta=meta)
    return job_service.get_job_read(db, job.id, actor=actor)


@router.post(
    "/installation-jobs/{job_id}/photos",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one installation photo (JPEG/PNG/WEBP, max 5 MB)",
)
def add_photo(
    job_id: JobId,
    db: DbSession,
    actor: Technician,
    meta: Meta,
    file: Annotated[UploadFile, File()],
) -> EvidenceRead:
    content = file.file.read(UPLOAD_READ_LIMIT)
    return job_service.add_photo(db, job_id, content, actor=actor, meta=meta)


@router.post(
    "/installation-jobs/{job_id}/complete",
    response_model=JobRead,
    summary="IN_PROGRESS -> COMPLETED with kW, power test and customer signature",
)
def complete_job(
    job_id: JobId, data: JobComplete, db: DbSession, actor: Technician, meta: Meta
) -> JobRead:
    job = job_service.complete_job(db, job_id, data, actor=actor, meta=meta)
    return job_service.get_job_read(db, job.id, actor=actor)


@router.get(
    "/evidence/{evidence_id}/file",
    response_class=Response,
    summary="Photo or signature file (cookie auth, works in <img>)",
)
def evidence_file(
    evidence_id: Annotated[int, Path(gt=0)], db: DbSession, actor: Staff
) -> Response:
    content, content_type = job_service.evidence_file(db, evidence_id)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/installation-jobs", response_model=Page[ScheduleRow])
def list_jobs(
    db: DbSession,
    actor: Planner,
    status: InstallationJobStatus = InstallationJobStatus.PLANNED,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ScheduleRow]:
    items, total = job_service.list_jobs(db, status, page=page, page_size=page_size)
    return Page[ScheduleRow](items=items, total=total, page=page, page_size=page_size)
