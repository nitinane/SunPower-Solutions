"""
FastAPI dependencies shared by all routes: DB session, logged-in user, role checks,
request metadata for the audit log.
"""

from collections.abc import Callable, Generator
from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.exceptions import Forbidden, Unauthorized
from app.models.users import User
from app.repositories import users as user_repo
from app.services.common import RequestMeta

SESSION_COOKIE = "sp_session"
SESSION_COOKIE_PATH = "/api"


def get_db() -> Generator[Session, None, None]:
    """One DB session per request, always closed (uncommitted work is rolled back)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_request_meta(request: Request) -> RequestMeta:
    """Request ID + client IP for the audit log."""
    return RequestMeta(
        request_id=getattr(request.state, "request_id", None),
        ip_address=request.client.host if request.client else None,
    )


def get_current_user(
    request: Request, db: Annotated[Session, Depends(get_db)]
) -> User:
    """Read the session cookie, verify the token, load the user. Any problem -> 401."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise Unauthorized("Please log in")
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise Unauthorized("Your session has expired. Please log in again") from None

    user = user_repo.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Please log in")
    return user


def require_role(*roles: str) -> Callable[..., User]:
    """Allow only these roles (admin is always allowed). Wrong role -> 403."""
    allowed = frozenset(roles) | {UserRole.ADMIN}

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise Forbidden("You do not have permission to do this")
        return user

    return dependency