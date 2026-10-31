"""
Installation day: the crew technician's phone form.

Flow: SCHEDULED -> START (material must be delivered) -> IN_PROGRESS -> photos ->
      COMPLETE (kW, power test, customer signature) -> COMPLETED; order -> installed.
Rules enforced here:
- Only a technician on this job's crew may start, upload or complete (403).
- Photos: max 10 per job, max 5 MB, type from the first bytes only (never the filename or
  the Content-Type header). Stored under a random key, never the uploaded name.
- Complete: power test must pass, at least one photo, real PNG signature 1 KB-500 KB.
  Hours = finish - start rounded UP to 0.25 h (minimum 0.25), same on every crew row.
Every change is written to audit_log in the same transaction.
"""

import base64
import binascii
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.dates import ist_date
from app.core.enums import (
    DispatchStatus,
    EvidenceType,
    InstallationJobStatus,
    OrderStatus,
    UserRole,
)
from app.exceptions import AppError, BusinessRuleViolation, Forbidden, NotFound, ValidationFailed
from app.models.customers import Customer, Site
from app.models.installations import InstallationEvidence, InstallationJob
from app.models.orders import Order
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import installations as job_repo
from app.repositories import orders as order_repo
from app.repositories import payments as payment_repo
from app.repositories import quotes as quote_repo
from app.schemas.installations import (
    CrewMember,
    EvidenceRead,
    InstalledLine,
    JobComplete,
    JobRead,
    ScheduleRow,
)
from app.schemas.quotes import QuoteSite
from app.services import dispatch as dispatch_service
from app.services.catalog import money
from app.services.common import RequestMeta
from app.storage import file_storage

MAX_PHOTOS = 10
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MIN_SIGNATURE_BYTES = 1024
MAX_SIGNATURE_BYTES = 500 * 1024
HOURS_STEP = timedelta(minutes=15)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class JobStatusInvalid(BusinessRuleViolation):
    code = "JOB_STATUS_INVALID"


class MaterialNotDelivered(BusinessRuleViolation):
    code = "MATERIAL_NOT_DELIVERED"


class PhotoLimitReached(BusinessRuleViolation):
    code = "PHOTO_LIMIT_REACHED"


class PhotoRequired(BusinessRuleViolation):
    code = "PHOTO_REQUIRED"


class FileTooLarge(AppError):
    code = "FILE_TOO_LARGE"
    status_code = 413


class FileTypeNotAllowed(ValidationFailed):
    code = "FILE_TYPE_NOT_ALLOWED"


class SignatureInvalid(ValidationFailed):
    code = "SIGNATURE_INVALID"


# ---------------------------------------------------------------- Read side

def site_read(site: Site) -> QuoteSite:
    return QuoteSite.model_validate(site, from_attributes=True)


def crew_by_job(db: Session, job_ids: list[int]) -> dict[int, list[CrewMember]]:
    crew: dict[int, list[CrewMember]] = {job_id: [] for job_id in job_ids}
    for row, user in job_repo.list_crew(db, job_ids):
        crew[row.job_id].append(
            CrewMember(user_id=user.id, name=user.full_name, hours=row.hours_worked)
        )
    return crew


def schedule_rows(
    db: Session, rows: list[tuple[InstallationJob, Order, Customer, Site]]
) -> list[ScheduleRow]:
    crew = crew_by_job(db, [job.id for job, *_ in rows])
    return [
        ScheduleRow(
            job_id=job.id,
            status=job.status,
            scheduled_date=ist_date(job.scheduled_at),
            order_id=order.id,
            order_number=order.order_number,
            customer_name=customer.full_name,
            customer_phone=customer.phone_e164,
            site=site_read(site),
            crew=crew[job.id],
        )
        for job, order, customer, site in rows
    ]


def get_job_read(db: Session, job_id: int, *, actor: User) -> JobRead:
    row = job_repo.job_with_order(db, job_id)
    if row is None:
        raise NotFound("Installation job not found")
    job, order, customer, site = row
    if actor.role == UserRole.TECHNICIAN:
        _require_crew(db, job, actor)

    lines: list[InstalledLine] = []
    dispatch = order_repo.get_pick_list(db, order.id)
    if dispatch is not None:
        for line in dispatch_service.to_read(db, dispatch).lines:
            lines.append(
                InstalledLine(
                    order_item_id=line.order_item_id,
                    sku=line.sku,
                    name=line.name,
                    qty=line.qty,
                    requires_serial=line.requires_serial,
                    serials=[s.serial for s in line.serials],
                )
            )
    signatures = job_repo.evidence_ids(db, job.id, EvidenceType.SIGNATURE)
    return JobRead(
        id=job.id,
        status=job.status,
        order_id=order.id,
        order_number=order.order_number,
        customer_name=customer.full_name,
        customer_phone=customer.phone_e164,
        site=site_read(site),
        scheduled_date=ist_date(job.scheduled_at),
        started_at=job.started_at,
        finished_at=job.completed_at,
        system_kw=job.installed_capacity_kw,
        power_test_passed=job.power_test_passed,
        signer_name=job.signed_by_name,
        crew=crew_by_job(db, [job.id])[job.id],
        lines=lines,
        photo_ids=job_repo.evidence_ids(db, job.id, EvidenceType.PHOTO),
        signature_id=signatures[-1] if signatures else None,
    )


def evidence_file(db: Session, evidence_id: int) -> tuple[bytes, str]:
    evidence = job_repo.get_evidence(db, evidence_id)
    if evidence is None:
        raise NotFound("File not found")
    try:
        return file_storage.open_bytes(evidence.storage_key), evidence.content_type
    except (FileNotFoundError, ValueError):
        raise NotFound("File not found") from None


# ---------------------------------------------------------------- Workflow actions

def start_job(
    db: Session, job_id: int, *, actor: User, meta: RequestMeta | None = None
) -> InstallationJob:
    job = _get_for_update(db, job_id)
    _require_crew(db, job, actor)
    _require_status(job, InstallationJobStatus.SCHEDULED, "Only a scheduled job can be started")
    dispatch = order_repo.get_pick_list(db, job.order_id)
    if dispatch is None or dispatch.status != DispatchStatus.DELIVERED:
        raise MaterialNotDelivered("The material for this order has not been delivered yet")

    old = snapshot(job)
    job_repo.update_job(
        db, job, {"status": InstallationJobStatus.IN_PROGRESS, "started_at": _now()}
    )
    audit(db, actor, "installation_job.started", "installation_job", job.id, old,
           snapshot(job), meta)
    db.commit()
    db.refresh(job)
    return job


def add_photo(
    db: Session,
    job_id: int,
    content: bytes,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> EvidenceRead:
    job = _get_for_update(db, job_id)
    _require_crew(db, job, actor)
    _require_status(
        job, InstallationJobStatus.IN_PROGRESS, "Photos can only be added while working"
    )
    if job_repo.count_evidence(db, job.id, EvidenceType.PHOTO) >= MAX_PHOTOS:
        raise PhotoLimitReached(f"A job can have at most {MAX_PHOTOS} photos")
    if len(content) > MAX_PHOTO_BYTES:
        raise FileTooLarge("Photo is larger than 5 MB", fields={"file": "Max 5 MB"})
    detected = sniff_image(content)
    if detected is None:
        raise FileTypeNotAllowed(
            "Only JPEG, PNG or WEBP photos are allowed", fields={"file": "Not a JPEG/PNG/WEBP"}
        )
    content_type, ext = detected

    evidence = _store_evidence(db, job, actor, EvidenceType.PHOTO, content, content_type, ext)
    audit(db, actor, "installation_job.photo_added", "installation_job", job.id, None,
           {"evidence_id": evidence.id, "size_bytes": len(content)}, meta)
    db.commit()
    db.refresh(evidence)
    return EvidenceRead.model_validate(evidence)


def complete_job(
    db: Session,
    job_id: int,
    data: JobComplete,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> InstallationJob:
    job = _get_for_update(db, job_id)
    _require_crew(db, job, actor)
    _require_status(job, InstallationJobStatus.IN_PROGRESS, "Only a started job can be completed")
    if not data.power_test_passed:
        raise ValidationFailed(
            "The power test must pass before the job can be completed",
            fields={"power_test_passed": "Must be true"},
        )
    if job_repo.count_evidence(db, job.id, EvidenceType.PHOTO) == 0:
        raise PhotoRequired("Add at least one installation photo first")
    signature = _decode_signature(data.signature_png_base64)

    finished = _now()
    hours = work_hours(job.started_at, finished)
    old = snapshot(job)
    sig = _store_evidence(db, job, actor, EvidenceType.SIGNATURE, signature, "image/png", "png")
    for row in job_repo.crew_rows_for_update(db, job.id):
        row.hours_worked = hours
    job_repo.update_job(
        db,
        job,
        {
            "status": InstallationJobStatus.COMPLETED,
            "completed_at": finished,
            "installed_capacity_kw": data.system_kw,
            "power_test_passed": True,
            "signed_by_name": data.signer_name,
            "signed_at": finished,
        },
    )
    audit(db, actor, "installation_job.completed", "installation_job", job.id, old,
           {**snapshot(job), "hours_per_technician": str(hours), "signature_id": sig.id}, meta)

    order = order_repo.get_by_id_for_update(db, job.order_id)
    quote = quote_repo.get_by_id(db, order.quote_id)
    fully_paid = money(payment_repo.sum_completed(db, order.id)) >= money(quote.total)
    new_status = OrderStatus.COMPLETED if fully_paid else OrderStatus.INSTALLED
    old_status = order.status
    order_repo.update(db, order, {"status": new_status})
    audit(db, actor, f"order.{new_status}", "order", order.id, {"status": old_status},
           {"status": new_status}, meta)

    db.commit()
    db.refresh(job)
    return job


# ---------------------------------------------------------------- Pure helpers (tested)

def sniff_image(content: bytes) -> tuple[str, str] | None:
    """(content type, extension) from the magic bytes, or None."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if content.startswith(PNG_MAGIC):
        return "image/png", "png"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def work_hours(started: datetime | None, finished: datetime) -> Decimal:
    """Elapsed time rounded UP to the next quarter hour, minimum 0.25."""
    elapsed = max(finished - started, timedelta(0)) if started else timedelta(0)
    quarters = max(1, -((-elapsed) // HOURS_STEP))
    return (Decimal(quarters) * Decimal("0.25")).quantize(Decimal("0.01"))


# ---------------------------------------------------------------- Internal helpers

def _decode_signature(value: str) -> bytes:
    raw = value.strip()
    if raw.startswith("data:"):
        raw = raw.partition(",")[2]
    invalid = SignatureInvalid(
        "The signature is missing or invalid. Ask the customer to sign again.",
        fields={"signature_png_base64": "Must be a signed PNG (1 KB to 500 KB)"},
    )
    try:
        content = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise invalid from None
    if not content.startswith(PNG_MAGIC):
        raise invalid
    if not MIN_SIGNATURE_BYTES <= len(content) <= MAX_SIGNATURE_BYTES:
        raise invalid
    return content


def _store_evidence(
    db: Session,
    job: InstallationJob,
    actor: User,
    kind: EvidenceType,
    content: bytes,
    content_type: str,
    ext: str,
) -> InstallationEvidence:
    key = file_storage.save_bytes(content, ext)
    return job_repo.add_evidence(
        db,
        {
            "job_id": job.id,
            "uploaded_by": actor.id,
            "evidence_type": kind,
            "storage_key": key,
            "content_type": content_type,
            "file_size_bytes": len(content),
            "captured_at": _now(),
        },
    )


def _get_for_update(db: Session, job_id: int) -> InstallationJob:
    job = job_repo.get_job(db, job_id, lock=True)
    if job is None:
        raise NotFound("Installation job not found")
    return job


def _require_crew(db: Session, job: InstallationJob, actor: User) -> None:
    if not job_repo.is_on_crew(db, job.id, actor.id):
        raise Forbidden("You are not on the crew for this job")


def _require_status(job: InstallationJob, expected: str, message: str) -> None:
    if job.status != expected:
        raise JobStatusInvalid(f"{message} (current status: {job.status})")


def _now() -> datetime:
    return datetime.now(UTC)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def snapshot(job: InstallationJob) -> dict[str, Any]:
    fields = ("status", "scheduled_at", "started_at", "completed_at", "installed_capacity_kw",
              "power_test_passed", "signed_by_name")
    return {field: _json_safe(getattr(job, field)) for field in fields}


def audit(
    db: Session,
    actor: User,
    action: str,
    entity_type: str,
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
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old,
        new_data=new,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )



def list_jobs(db: Session, status: InstallationJobStatus, *, page: int, page_size: int):
    rows, total = job_repo.jobs_page(db, status, limit=page_size, offset=(page - 1) * page_size)
    return schedule_rows(db, rows), total
