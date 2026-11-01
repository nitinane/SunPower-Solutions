"""Read the audit trail of any record as a timeline (who did what, when)."""

from sqlalchemy.orm import Session

from app.repositories import auth as audit_repo
from app.schemas.auth import AuditEntryRead


def list_history(db: Session, entity_type: str, entity_id: int) -> list[AuditEntryRead]:
    """Oldest first. 'Customer' is shown when no employee did it (e.g. the web form)."""
    rows = audit_repo.list_for_entity(db, entity_type, entity_id)
    return [
        AuditEntryRead(
            id=entry.id,
            action=entry.action,
            actor_user_id=entry.actor_user_id,
            actor_name=actor_name or ("Customer" if entry.actor_user_id is None else None),
            old_data=entry.old_data,
            new_data=entry.new_data,
            created_at=entry.created_at,
        )
        for entry, actor_name in rows
    ]