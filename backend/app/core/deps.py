from collections.abc import Callable, Generator
from sqlalchemy.orm import Session
from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user() -> None:
    """Authentication stub; implement with the auth domain."""
    raise NotImplementedError("Authentication is not implemented")


def require_role(*roles: str) -> Callable[..., None]:
    """Role authorization stub; implement with the user domain."""
    def dependency() -> None:
        _ = roles
        raise NotImplementedError("Role authorization is not implemented")
    return dependency
