"""
Login / logout / who am I.

The session token travels only in an httpOnly cookie:
- httponly  -> JavaScript can't read it (XSS can't steal it)
- samesite  -> browsers don't send it from other sites (CSRF protection)
- secure    -> HTTPS only in production
- path=/api -> only sent to the API
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    SESSION_COOKIE,
    SESSION_COOKIE_PATH,
    get_current_user,
    get_db,
    get_request_meta,
)
from app.models.users import User
from app.schemas.auth import CurrentUser, LoginRequest, LoginResponse
from app.services import auth as auth_service
from app.services.common import RequestMeta

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]
Meta = Annotated[RequestMeta, Depends(get_request_meta)]


def _cookie_is_secure() -> bool:
    return settings.env.lower() == "production"


@router.post("/login", response_model=LoginResponse, summary="Log in with email + password")
def login(data: LoginRequest, response: Response, db: DbSession, meta: Meta) -> LoginResponse:
    result = auth_service.login(db, data, meta=meta)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=result.token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=_cookie_is_secure(),
        samesite="strict",
        path=SESSION_COOKIE_PATH,
    )
    return LoginResponse(user=CurrentUser.model_validate(result.user), expires_at=result.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out")
def logout(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path=SESSION_COOKIE_PATH,
        httponly=True,
        secure=_cookie_is_secure(),
        samesite="strict",
    )


@router.get("/me", response_model=CurrentUser, summary="The logged-in user")
def me(user: Annotated[User, Depends(get_current_user)]) -> CurrentUser:
    return CurrentUser.model_validate(user)