"""Warranty inserts; the caller owns the transaction."""

from sqlalchemy.orm import Session

from app.models.warranties import Warranty


def create(db: Session, **values) -> Warranty:
    warranty = Warranty(**values)
    db.add(warranty)
    db.flush()
    return warranty
