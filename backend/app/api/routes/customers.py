"""Customer read endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.enums import UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.customers import CustomerListItem, CustomerRead
from app.services import customers as customer_service

router = APIRouter(prefix="/customers", tags=["customers"])
DbSession = Annotated[Session, Depends(get_db)]
CustomerId = Annotated[int, Path(gt=0)]
CustomerStaff = Annotated[
    User,
    Depends(require_role(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.OFFICE, UserRole.SUPPORT)),
]


@router.get("", response_model=Page[CustomerListItem])
def list_customers(
    db: DbSession,
    _actor: CustomerStaff,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[CustomerListItem]:
    return customer_service.list_customers(db, page=page, page_size=page_size, search=search)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: CustomerId, db: DbSession, _actor: CustomerStaff) -> CustomerRead:
    return customer_service.get_customer(db, customer_id)
