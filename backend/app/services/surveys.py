"""
Feature 2: Site survey + approval gate.

PDF: "If it looks good, a technician visits to measure the roof direction, tilt and cable
distance. Only after the survey is approved should the customer receive a quote."

Flow:  qualified enquiry -> scheduled -> submitted (measurements) -> approved | rejected
Rules enforced here:
- Only a qualified enquiry (with a site) can get a survey; one open survey per enquiry.
- Only active surveyors/technicians can be booked.
- Only the assigned surveyor can submit; field staff only ever see their own surveys.
- The reviewer can never be the surveyor (also a DB CHECK). Rejecting needs a reason.
- require_approved_survey() is the gate the quote feature calls before creating a quote.
Every change is written to audit_log in the same transaction.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import EnquiryStatus, SurveyStatus, UserRole
from app.exceptions import BusinessRuleViolation, Conflict, Forbidden, NotFound, ValidationFailed
from app.models.enquiries import Enquiry
from app.models.surveys import SiteSurvey
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import enquiries as enquiry_repo
from app.repositories import surveys as survey_repo
from app.repositories import users as user_repo
from app.schemas.surveys import SurveyRead, SurveyReject, SurveySchedule, SurveySubmit
from app.services.common import RequestMeta

FIELD_ROLES = frozenset({UserRole.SURVEYOR, UserRole.TECHNICIAN})
MAX_PAGE_SIZE = 100

AUDIT_FIELDS = (
    "status",
    "surveyor_id",
    "scheduled_at",
    "submitted_at",
    "roof_direction",
    "roof_tilt_deg",
    "cable_distance_m",
    "reviewed_by",
    "reviewed_at",
    "rejection_reason",
)


# ---------------------------------------------------------------- Read side

def to_read(survey: SiteSurvey, enquiry: Enquiry | None) -> SurveyRead:
    """Survey + who/where to visit, so the surveyor's phone screen has everything."""
    read = SurveyRead.model_validate(survey)
    if enquiry is None:
        return read
    return read.model_copy(
        update={
            "contact_name": enquiry.contact_name,
            "contact_phone": enquiry.phone_e164,
            "address_line": enquiry.address_line,
            "city": enquiry.city,
            "pincode": enquiry.pincode,
        }
    )


def get_survey(db: Session, survey_id: int, *, actor: User) -> tuple[SiteSurvey, Enquiry]:
    """One survey. Field staff get 404 for surveys that are not theirs."""
    survey = survey_repo.get_by_id(db, survey_id)
    if survey is None or not _can_view(actor, survey):
        raise NotFound("Survey not found")
    return survey, enquiry_repo.get_by_id(db, survey.enquiry_id)


def list_surveys(
    db: Session,
    *,
    actor: User,
    status: SurveyStatus | None = None,
    mine: bool = False,
    enquiry_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[SiteSurvey, Enquiry]], int]:
    """Office/director see all; surveyors and technicians always see only their own."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    surveyor_id = actor.id if (mine or actor.role in FIELD_ROLES) else None
    return survey_repo.list_page(
        db,
        status=status,
        surveyor_id=surveyor_id,
        enquiry_id=enquiry_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )


def require_approved_survey(db: Session, survey_id: int, enquiry_id: int) -> SiteSurvey:
    """The quote gate: the survey must exist, belong to this enquiry and be approved."""
    survey = survey_repo.get_by_id(db, survey_id)
    if survey is None or survey.enquiry_id != enquiry_id:
        raise NotFound("Survey not found for this enquiry")
    if survey.status != SurveyStatus.APPROVED:
        raise BusinessRuleViolation("A quote can only be made after the site survey is approved")
    return survey


# ---------------------------------------------------------------- Workflow actions

def schedule_survey(
    db: Session,
    enquiry_id: int,
    data: SurveySchedule,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> tuple[SiteSurvey, Enquiry]:
    """Book a surveyor for a qualified enquiry."""
    enquiry = enquiry_repo.get_by_id_for_update(db, enquiry_id)  # lock: no double booking
    if enquiry is None:
        raise NotFound("Enquiry not found")
    if enquiry.status != EnquiryStatus.QUALIFIED or enquiry.site_id is None:
        raise BusinessRuleViolation("Only a qualified enquiry can get a site survey")
    if survey_repo.find_open_for_enquiry(db, enquiry.id) is not None:
        raise Conflict("This enquiry already has a scheduled or submitted survey")

    surveyor = user_repo.get_by_id(db, data.surveyor_id)
    if surveyor is None or not surveyor.is_active or surveyor.role not in FIELD_ROLES:
        raise ValidationFailed(
            "Cannot book this person for a survey",
            fields={"surveyor_id": "Choose an active surveyor or technician"},
        )

    survey = survey_repo.create(
        db,
        {
            "enquiry_id": enquiry.id,
            "site_id": enquiry.site_id,
            "surveyor_id": surveyor.id,
            "status": SurveyStatus.SCHEDULED,
            "scheduled_at": data.scheduled_at,
        },
    )
    _audit(db, actor, "survey.scheduled", survey, None, _snapshot(survey), meta)
    db.commit()
    db.refresh(survey)
    return survey, enquiry


def submit_survey(
    db: Session,
    survey_id: int,
    data: SurveySubmit,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> tuple[SiteSurvey, Enquiry]:
    """Surveyor saves the roof measurements; the survey then waits for review."""
    survey = _get_for_update(db, survey_id, actor)
    if actor.role != UserRole.ADMIN and survey.surveyor_id != actor.id:
        raise Forbidden("Only the assigned surveyor can submit this survey")
    _require_status(survey, SurveyStatus.SCHEDULED, "Only a scheduled survey can be submitted")

    old = _snapshot(survey)
    survey_repo.update(
        db,
        survey,
        {
            "roof_direction": data.roof_direction,
            "roof_tilt_deg": data.roof_tilt_deg,
            "cable_distance_m": data.cable_distance_m,
            "findings": data.findings,
            "status": SurveyStatus.SUBMITTED,
            "submitted_at": _now(),
        },
    )
    _audit(db, actor, "survey.submitted", survey, old, _snapshot(survey), meta)
    db.commit()
    db.refresh(survey)
    return survey, enquiry_repo.get_by_id(db, survey.enquiry_id)


def approve_survey(
    db: Session, survey_id: int, *, actor: User, meta: RequestMeta | None = None
) -> tuple[SiteSurvey, Enquiry]:
    """Approve a submitted survey. This unlocks quoting for the enquiry."""
    return _review(db, survey_id, actor, SurveyStatus.APPROVED, None, meta)


def reject_survey(
    db: Session,
    survey_id: int,
    data: SurveyReject,
    *,
    actor: User,
    meta: RequestMeta | None = None,
) -> tuple[SiteSurvey, Enquiry]:
    """Reject a submitted survey with a reason. Office can book a new survey afterwards."""
    return _review(db, survey_id, actor, SurveyStatus.REJECTED, data.reason, meta)


# ---------------------------------------------------------------- Internal helpers

def _review(
    db: Session,
    survey_id: int,
    actor: User,
    decision: SurveyStatus,
    reason: str | None,
    meta: RequestMeta | None,
) -> tuple[SiteSurvey, Enquiry]:
    survey = _get_for_update(db, survey_id, actor)
    _require_status(survey, SurveyStatus.SUBMITTED, "Only a submitted survey can be reviewed")
    if survey.surveyor_id == actor.id:
        raise Forbidden("You cannot review a survey you carried out")

    old = _snapshot(survey)
    survey_repo.update(
        db,
        survey,
        {
            "status": decision,
            "reviewed_by": actor.id,
            "reviewed_at": _now(),
            "rejection_reason": reason,
        },
    )
    _audit(db, actor, f"survey.{decision}", survey, old, _snapshot(survey), meta)
    db.commit()
    db.refresh(survey)
    return survey, enquiry_repo.get_by_id(db, survey.enquiry_id)


def _now() -> datetime:
    return datetime.now(UTC)


def _can_view(actor: User, survey: SiteSurvey) -> bool:
    return actor.role not in FIELD_ROLES or survey.surveyor_id == actor.id


def _get_for_update(db: Session, survey_id: int, actor: User) -> SiteSurvey:
    survey = survey_repo.get_by_id_for_update(db, survey_id)
    if survey is None or not _can_view(actor, survey):
        raise NotFound("Survey not found")
    return survey


def _require_status(survey: SiteSurvey, expected: SurveyStatus, message: str) -> None:
    if survey.status != expected:
        raise BusinessRuleViolation(f"{message} (current status: {survey.status})")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _snapshot(survey: SiteSurvey) -> dict[str, Any]:
    return {field: _json_safe(getattr(survey, field, None)) for field in AUDIT_FIELDS}


def _audit(
    db: Session,
    actor: User,
    action: str,
    survey: SiteSurvey,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
    meta: RequestMeta | None,
) -> None:
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id,
        action=action,
        entity_type="site_survey",
        entity_id=survey.id,
        old_data=old,
        new_data=new,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )