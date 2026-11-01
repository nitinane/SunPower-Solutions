"""Catalog HTTP layer: package templates with parts list and price preview (office, director)."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_role
from app.core.enums import PackageType, UserRole
from app.models.users import User
from app.schemas.catalog import PackageRead, ProductRead
from app.schemas.common import Page
from app.services import catalog as catalog_service

router = APIRouter(tags=["catalog"])

DbSession = Annotated[Session, Depends(get_db)]
Sales = Annotated[User, Depends(require_role(UserRole.OFFICE, UserRole.DIRECTOR))]


@router.get("/packages", response_model=list[PackageRead], summary="Active package templates")
def list_packages(
    db: DbSession,
    actor: Sales,
    package_type: PackageType | None = None,
    kw: Annotated[Decimal | None, Query(gt=0, le=100)] = None,
) -> list[PackageRead]:
    return catalog_service.list_packages(db, package_type=package_type, kw=kw)


PartsViewer = Annotated[User, Depends(require_role(
    UserRole.SUPPORT, UserRole.TECHNICIAN, UserRole.OFFICE,
    UserRole.WAREHOUSE, UserRole.DIRECTOR,
))]


@router.get("/products", response_model=Page[ProductRead])
def list_products(
    db: DbSession, actor: PartsViewer, search: str = "",
    requires_serial: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ProductRead]:
    items, total = catalog_service.list_products(
        db, search=search, requires_serial=requires_serial, page=page, page_size=page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)
