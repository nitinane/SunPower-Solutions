"""
Feature 2 HTTP layer: site survey + approval gate.

Who can do what:
- office / director : book a survey for a qualified enquiry
- surveyor / technician : see their own surveys, submit measurements
- director : approve or reject (admin is always allowed)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import SurveyStatus, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.surveys import SurveyRead, SurveyReject, SurveySchedule, SurveySubmit
from app.services import surveys as survey_service
from app.services.common import RequestMeta

router = APIRouter(tags=["surveys"])

DbSession = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Scheduler = Annotated[User, Depends(require_role(UserRole.OFFICE, UserRole.DIRECTOR))]
Viewer = Annotated[
    User,
    Depends(
        require_role(UserRole.OFFICE, UserRole.DIRECTOR, UserRole.SURVEYOR, UserRole.TECHNICIAN)
    ),
]
FieldStaff = Annotated[User, Depends(require_role(UserRole.SURVEYOR, UserRole.TECHNICIAN))]
Reviewer = Annotated[User, Depends(require_role(UserRole.DIRECTOR))]
SurveyId = Annotated[int, Path(gt=0)]


@router.post(
    "/enquiries/{enquiry_id}/surveys",
    response_model=SurveyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Book a site survey for a qualified enquiry",
)
def schedule_survey(
    enquiry_id: Annotated[int, Path(gt=0)],
    data: SurveySchedule,
    db: DbSession,
    actor: Scheduler,
    meta: Meta,
) -> SurveyRead:
    survey, enquiry = survey_service.schedule_survey(db, enquiry_id, data, actor=actor, meta=meta)
    return survey_service.to_read(survey, enquiry)


@router.get("/surveys", response_model=Page[SurveyRead], summary="Surveys (field staff: own only)")
def list_surveys(
    db: DbSession,
    actor: Viewer,
    status_filter: Annotated[SurveyStatus | None, Query(alias="status")] = None,
    mine: bool = False,
    enquiry_id: Annotated[int | None, Query(gt=0)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[SurveyRead]:
    rows, total = survey_service.list_surveys(
        db,
        actor=actor,
        status=status_filter,
        mine=mine,
        enquiry_id=enquiry_id,
        page=page,
        page_size=page_size,
    )
    return Page[SurveyRead](
        items=[survey_service.to_read(survey, enquiry) for survey, enquiry in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/surveys/{survey_id}", response_model=SurveyRead, summary="One survey")
def get_survey(survey_id: SurveyId, db: DbSession, actor: Viewer) -> SurveyRead:
    survey, enquiry = survey_service.get_survey(db, survey_id, actor=actor)
    return survey_service.to_read(survey, enquiry)


@router.post(
    "/surveys/{survey_id}/submit",
    response_model=SurveyRead,
    summary="Surveyor submits roof direction, tilt and cable distance",
)
def submit_survey(
    survey_id: SurveyId, data: SurveySubmit, db: DbSession, actor: FieldStaff, meta: Meta
) -> SurveyRead:
    survey, enquiry = survey_service.submit_survey(db, survey_id, data, actor=actor, meta=meta)
    return survey_service.to_read(survey, enquiry)


@router.post("/surveys/{survey_id}/approve", response_model=SurveyRead, summary="Approve")
def approve_survey(survey_id: SurveyId, db: DbSession, actor: Reviewer, meta: Meta) -> SurveyRead:
    survey, enquiry = survey_service.approve_survey(db, survey_id, actor=actor, meta=meta)
    return survey_service.to_read(survey, enquiry)


@router.post("/surveys/{survey_id}/reject", response_model=SurveyRead, summary="Reject")
def reject_survey(
    survey_id: SurveyId, data: SurveyReject, db: DbSession, actor: Reviewer, meta: Meta
) -> SurveyRead:
    survey, enquiry = survey_service.reject_survey(db, survey_id, data, actor=actor, meta=meta)
    return survey_service.to_read(survey, enquiry)