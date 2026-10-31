"""IST reporting periods and hashed read-only dashboard shares."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.exceptions import BusinessRuleViolation, NotFound
from app.repositories import auth as audit_repo
from app.repositories import dashboard as repo
from app.schemas.dashboard import DashboardSummary, ShareRead
from app.services.common import RequestMeta

BUSINESS_TZ = ZoneInfo("Asia/Kolkata")


class ShareRevoked(BusinessRuleViolation):
    code = "SHARE_ALREADY_REVOKED"


def _now():
    return datetime.now(UTC)


def summary(db, period):
    end = _now()
    local = end.astimezone(BUSINESS_TZ)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start -= timedelta(days=start.weekday())
    elif period == "month":
        start = start.replace(day=1)
    start = start.astimezone(UTC)
    cards, jobs, unfinished, repairs = repo.summary_blocks(db, start, end, local.date())
    return DashboardSummary(
        period=period,
        from_at=start,
        to_at=end,
        cards=cards,
        profit_per_job=jobs,
        unfinished_jobs=unfinished,
        open_repairs=repairs,
    )


def create_share(db, data, *, actor, meta=None):
    token = secrets.token_urlsafe(32)
    row = repo.create_share(
        db,
        token_hash=_hash(token),
        period=data.period,
        expires_at=_now() + timedelta(hours=data.expires_in_hours),
        created_by=actor.id,
    )
    _audit(
        db,
        actor,
        "dashboard.share_created",
        row,
        {"period": row.period, "expires_at": row.expires_at.isoformat()},
        meta,
    )
    db.commit()
    db.refresh(row)
    return ShareRead(id=row.id, url=f"/share/{token}", expires_at=row.expires_at)


def revoke(db, share_id, *, actor, meta=None):
    row = repo.share_by_id_for_update(db, share_id)
    if row is None:
        raise NotFound("Share link not found")
    if row.revoked_at is not None:
        raise ShareRevoked("Share link is already revoked")
    repo.revoke(db, row, _now())
    _audit(
        db, actor, "dashboard.share_revoked", row, {"revoked_at": row.revoked_at.isoformat()}, meta
    )
    db.commit()


def public_summary(db, token):
    row = repo.active_share(db, _hash(token), _now())
    if row is None:
        raise NotFound("Dashboard not found")
    return summary(db, row.period)


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _audit(db, actor, action, row, new, meta):
    meta = meta or RequestMeta()
    audit_repo.add_audit(
        db,
        actor_user_id=actor.id,
        action=action,
        entity_type="dashboard_share",
        entity_id=row.id,
        new_data=new,
        request_id=meta.request_id,
        ip_address=meta.ip_address,
    )
