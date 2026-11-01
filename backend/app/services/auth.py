"""
Login. The service checks credentials and creates the session token; the route puts the
token in an httpOnly cookie, so JavaScript can never read it (protects against XSS theft).

Security rules:
- Same error for "no such user", "wrong password" and "inactive user", so nobody can probe
  which emails exist.
- When the email is unknown we still run one password hash, so the response time does not
  reveal it either.
- Every successful login is written to audit_log; failures are logged on the server.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cache

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.exceptions import Unauthorized
from app.models.users import User
from app.repositories import auth as audit_repo
from app.repositories import users as user_repo
from app.schemas.auth import LoginRequest
from app.services.common import RequestMeta

logger = logging.getLogger(__name__)

INVALID_LOGIN = "Invalid email or password"


@dataclass(frozen=True)
class LoginResult:
    user: User
    token: str
    expires_at: datetime


def login(db: Session, data: LoginRequest, *, meta: RequestMeta | None = None) -> LoginResult:
    """Check email + password and create a session token."""
    meta = meta or RequestMeta()
    user = user_repo.get_by_email(db, data.email)

    if user is None:
        verify_password(data.password, _dummy_hash())  # equal timing for unknown emails
        _log_failure(data.email, "unknown_email", meta)
        raise Unauthorized(INVALID_LOGIN)
    if not verify_password(data.password, user.password_hash):
        _log_failure(data.email, "wrong_password", meta)
        raise Unauthorized(INVALID_LOGIN)
    if not user.is_active:
        _log_failure(data.email, "inactive_user", meta)
        raise Unauthorized(INVALID_LOGIN)

    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    token = create_access_token(str(user.id))

    audit_repo.add_audit(
        db,
        actor_user_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )
    db.commit()
    db.refresh(user)
    return LoginResult(user=user, token=token, expires_at=expires_at)


@cache
def _dummy_hash() -> str:
    """A real Argon2 hash of a random value, created once, used only to equalise timing."""
    return hash_password("timing-equaliser-not-a-real-password")


def _log_failure(email: str, reason: str, meta: RequestMeta) -> None:
    logger.warning(
        "Login failed",
        extra={
            "email": email,
            "reason": reason,
            "ip": meta.ip_address,
            "request_id": meta.request_id,
        },
    )