from collections.abc import Callable, Generator
from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.exceptions import Forbidden, Unauthorized
from app.models.users import User
from app.repositories import users as user_repo

SESSION_COOKIE = "sp_session"
SESSION_COOKIE_PATH = "/"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the signed, HttpOnly browser session to an active database user."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise Unauthorized("Please log in")
    try:
        subject = decode_access_token(token).get("sub")
        user_id = int(subject)
    except (ValueError, TypeError, jwt.PyJWTError) as exc:
        raise Unauthorized("Your session is invalid or expired. Please log in again") from exc
    user = user_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Please log in")
    return user


def require_role(*roles: str) -> Callable[..., User]:
    """Require an authenticated user whose role is in the allowed set."""

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in {str(role) for role in roles}:
            raise Forbidden("Your role cannot access this resource")
        return user

    return dependency
