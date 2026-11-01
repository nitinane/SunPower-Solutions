"""Customer, serial, and warranty lookup for support staff."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.tickets import SupportResult
from app.services import tickets as service

router = APIRouter(prefix="/support", tags=["support"])


@router.get("/search", response_model=list[SupportResult])
def search(
    q: Annotated[str, Query(min_length=1, max_length=150)],
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[
        User, Depends(require_role(UserRole.SUPPORT, UserRole.OFFICE, UserRole.DIRECTOR))
    ],
) -> list[SupportResult]:
    return service.search(db, q)
