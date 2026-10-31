"""Audit log writes and reads. The audit log is append-only: no update or delete functions."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog


def add_audit(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    note: str | None = None,
) -> AuditLog:
    """Stage one audit row; it is saved by the same commit as the change it describes."""
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        request_id=request_id,
        ip_address=ip_address,
        note=note,
    )
    db.add(entry)
    return entry


def list_for_entity(
    db: Session, entity_type: str, entity_id: int, limit: int = 100
) -> list[AuditLog]:
    """History of one record, oldest first (for a timeline on the detail screen)."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at, AuditLog.id)
        .limit(limit)
    )
    return list(db.scalars(stmt))