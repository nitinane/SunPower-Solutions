"""Staff login with database-backed password verification."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from pwdlib.exceptions import UnknownHashError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import SESSION_COOKIE, SESSION_COOKIE_PATH, get_current_user, get_db
from app.core.security import create_access_token, verify_password
from app.exceptions import Unauthorized
from app.models.users import User
from app.repositories import users as user_repo
from app.schemas.auth import CurrentUser, LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=LoginResponse)
def login(
    data: LoginRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    user = user_repo.get_by_email(db, str(data.email))
    if user is None or not user.is_active:
        raise Unauthorized("Email or password is incorrect")
    try:
        valid = verify_password(data.password, user.password_hash)
    except (ValueError, TypeError, UnknownHashError):
        valid = False
    if not valid:
        raise Unauthorized("Email or password is incorrect")
    token = create_access_token(str(user.id))
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,
        secure=settings.env.lower() == "production",
        samesite="lax",
        path=SESSION_COOKIE_PATH,
    )
    return LoginResponse(
        user=CurrentUser.model_validate(user),
        expires_at=datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path=SESSION_COOKIE_PATH,
        httponly=True,
        secure=settings.env.lower() == "production",
        samesite="lax",
    )


@router.get("/me", response_model=CurrentUser)
def me(user: Annotated[User, Depends(get_current_user)]) -> CurrentUser:
    return CurrentUser.model_validate(user)
