"""Installation job reads and authorized evidence retrieval."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.enums import InstallationJobStatus, UserRole
from app.exceptions import NotFound
from app.models.customers import Customer, Site
from app.models.installations import InstallationEvidence, InstallationJob, JobTechnician
from app.models.orders import Order
from app.models.users import User
from app.schemas.installations import EvidenceRead, InstallationRead, TechnicianAssignmentRead
from app.storage.file_storage import read_file

router = APIRouter(prefix="/installations", tags=["installations"])
Db = Annotated[Session, Depends(get_db)]
Staff = Annotated[
    User,
    Depends(require_role(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.OFFICE, UserRole.TECHNICIAN)),
]


def _read(db: Session, job: InstallationJob) -> InstallationRead:
    order = db.get(Order, job.order_id)
    customer = db.get(Customer, order.customer_id)
    site = db.get(Site, job.site_id)
    assignments = db.execute(
        select(JobTechnician, User.full_name)
        .join(User, User.id == JobTechnician.technician_id)
        .where(JobTechnician.job_id == job.id)
        .order_by(User.full_name)
    ).all()
    evidence = list(
        db.scalars(
            select(InstallationEvidence)
            .where(InstallationEvidence.job_id == job.id)
            .order_by(InstallationEvidence.id)
        )
    )
    return InstallationRead(
        id=job.id,
        order_id=job.order_id,
        order_number=order.order_number,
        customer_id=customer.id,
        customer_name=customer.full_name,
        site_id=site.id,
        site_name=site.site_name,
        city=site.city,
        status=job.status,
        scheduled_at=job.scheduled_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        completion_notes=job.completion_notes,
        installed_capacity_kw=job.installed_capacity_kw,
        power_test_passed=job.power_test_passed,
        signed_by_name=job.signed_by_name,
        signed_at=job.signed_at,
        technicians=[
            TechnicianAssignmentRead.model_validate({**assignment.__dict__, "full_name": name})
            for assignment, name in assignments
        ],
        evidence=[EvidenceRead.model_validate(item) for item in evidence],
    )


def _restrict_technician(stmt, actor: User):
    """Technicians only see jobs assigned to themselves."""
    if actor.role == UserRole.TECHNICIAN:
        assigned = select(JobTechnician.job_id).where(
            JobTechnician.job_id == InstallationJob.id,
            JobTechnician.technician_id == actor.id,
        )
        stmt = stmt.where(assigned.exists())
    return stmt


@router.get("", response_model=list[InstallationRead])
def list_installations(
    db: Db,
    actor: Staff,
    status: Annotated[InstallationJobStatus | None, Query()] = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
) -> list[InstallationRead]:
    stmt = select(InstallationJob)
    stmt = _restrict_technician(stmt, actor)
    if status:
        stmt = stmt.where(InstallationJob.status == status)
    if scheduled_from:
        stmt = stmt.where(InstallationJob.scheduled_at >= scheduled_from)
    if scheduled_to:
        stmt = stmt.where(InstallationJob.scheduled_at <= scheduled_to)
    return [
        _read(db, job)
        for job in db.scalars(
            stmt.order_by(InstallationJob.scheduled_at.nullslast(), InstallationJob.id)
        )
    ]


@router.get("/{job_id}", response_model=InstallationRead)
def get_installation(job_id: Annotated[int, Path(gt=0)], db: Db, actor: Staff) -> InstallationRead:
    stmt = _restrict_technician(select(InstallationJob).where(InstallationJob.id == job_id), actor)
    job = db.scalars(stmt).first()
    if job is None:
        raise NotFound("Installation job not found")
    return _read(db, job)


@router.get("/{job_id}/evidence/{evidence_id}")
def get_evidence(job_id: int, evidence_id: int, db: Db, actor: Staff) -> Response:
    visible_job = _restrict_technician(
        select(InstallationJob).where(InstallationJob.id == job_id), actor
    )
    if db.scalars(visible_job).first() is None:
        raise NotFound("Installation evidence not found")
    evidence = db.scalar(
        select(InstallationEvidence).where(
            InstallationEvidence.id == evidence_id, InstallationEvidence.job_id == job_id
        )
    )
    if evidence is None:
        raise NotFound("Installation evidence not found")
    return Response(
        read_file(evidence.storage_key),
        media_type=evidence.content_type,
        headers={"Content-Disposition": "inline"},
    )
