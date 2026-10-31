"""Ticket actions with explicit role protection."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import TicketStatus, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.tickets import TicketAssign, TicketConfirm, TicketCreate, TicketRead, TicketResolve
from app.services import tickets as service
from app.services.common import RequestMeta

router = APIRouter(prefix="/tickets", tags=["tickets"])
Db = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Creator = Annotated[User, Depends(require_role(UserRole.SUPPORT, UserRole.OFFICE))]
Viewer = Annotated[
    User,
    Depends(
        require_role(
            UserRole.SUPPORT,
            UserRole.MANAGER,
            UserRole.DIRECTOR,
            UserRole.TECHNICIAN,
        )
    ),
]
Assigner = Annotated[User, Depends(require_role(UserRole.SUPPORT, UserRole.MANAGER))]
Resolver = Annotated[User, Depends(require_role(UserRole.SUPPORT, UserRole.TECHNICIAN))]
TicketId = Annotated[int, Path(gt=0)]


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(data: TicketCreate, db: Db, actor: Creator, meta: Meta) -> TicketRead:
    return service.to_read(db, service.create_ticket(db, data, actor=actor, meta=meta))


@router.get("", response_model=Page[TicketRead])
def list_tickets(
    db: Db,
    actor: Viewer,
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
    assigned_to_me: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[TicketRead]:
    items, total = service.list_tickets(
        db,
        actor=actor,
        status=status_filter,
        assigned_to_me=assigned_to_me,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: TicketId, db: Db, actor: Viewer) -> TicketRead:
    return service.to_read(db, service.get_ticket(db, ticket_id, actor=actor))


@router.post("/{ticket_id}/assign", response_model=TicketRead)
def assign(
    ticket_id: TicketId, data: TicketAssign, db: Db, actor: Assigner, meta: Meta
) -> TicketRead:
    return service.to_read(db, service.assign(db, ticket_id, data, actor=actor, meta=meta))


@router.post("/{ticket_id}/resolve", response_model=TicketRead)
def resolve(
    ticket_id: TicketId, data: TicketResolve, db: Db, actor: Resolver, meta: Meta
) -> TicketRead:
    return service.to_read(db, service.resolve(db, ticket_id, data, actor=actor, meta=meta))


@router.post("/{ticket_id}/confirm", response_model=TicketRead)
def confirm(
    ticket_id: TicketId, data: TicketConfirm, db: Db, actor: Creator, meta: Meta
) -> TicketRead:
    return service.to_read(db, service.confirm(db, ticket_id, data, actor=actor, meta=meta))
