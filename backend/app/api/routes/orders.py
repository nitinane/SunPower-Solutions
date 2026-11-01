"""
Orders HTTP layer. Recording the first payment confirms the order and creates the
pick list + installation job (all rules in app/services/orders.py).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_request_meta, require_role
from app.core.enums import OrderStatus, UserRole
from app.models.users import User
from app.schemas.common import Page
from app.schemas.orders import OrderRead, OrderSummary, PaymentCreate, PaymentRead, PaymentResult
from app.services import orders as order_service
from app.services.common import RequestMeta

router = APIRouter(prefix="/orders", tags=["orders"])

DbSession = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]
Cashier = Annotated[User, Depends(require_role(UserRole.OFFICE, UserRole.DIRECTOR))]
Lister = Annotated[
    User, Depends(require_role(UserRole.OFFICE, UserRole.MANAGER, UserRole.DIRECTOR))
]
Viewer = Annotated[
    User, Depends(require_role(
        UserRole.OFFICE, UserRole.MANAGER, UserRole.WAREHOUSE, UserRole.DIRECTOR
    ))
]
OrderId = Annotated[int, Path(gt=0)]
IdempotencyKey = Annotated[
    str | None,
    Header(max_length=100, description="Same key = same result (safe retries)"),
]


@router.post(
    "/{order_id}/payments",
    response_model=PaymentResult,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment (first payment confirms the order)",
)
def record_payment(
    order_id: OrderId,
    data: PaymentCreate,
    response: Response,
    db: DbSession,
    actor: Cashier,
    meta: Meta,
    idempotency_key: IdempotencyKey = None,
) -> PaymentResult:
    outcome = order_service.record_payment(
        db, order_id, data, actor=actor, idempotency_key=idempotency_key, meta=meta
    )
    if not outcome.created:
        response.status_code = status.HTTP_200_OK
    return PaymentResult(
        payment=PaymentRead.model_validate(outcome.payment),
        order=order_service.to_read(db, outcome.order),
    )


@router.get("", response_model=Page[OrderSummary], summary="Orders")
def list_orders(
    db: DbSession,
    actor: Lister,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[OrderSummary]:
    items, total = order_service.list_orders(
        db, status=status_filter, search=search, page=page, page_size=page_size
    )
    return Page[OrderSummary](items=items, total=total, page=page, page_size=page_size)


@router.get("/{order_id}", response_model=OrderRead, summary="Order detail")
def get_order(order_id: OrderId, db: DbSession, actor: Viewer) -> OrderRead:
    return order_service.to_read(db, order_service.get_order(db, order_id))
