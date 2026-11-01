"""Small cache-aside helpers for explicitly approved, non-sensitive read models."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any, TypeVar

import redis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)
T = TypeVar("T")

CACHE_PREFIX = "sunpower:v1"
CACHE_TTLS: dict[str, int] = {
    "dashboard_summary": 30,
    "financial_report": 60,
    "solar_packages": 300,
    "product_catalog": 300,
    "enum_metadata": 3600,
}


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
        health_check_interval=30,
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def cache_key(domain: str, permission_scope: str, resource: str) -> str:
    """Build a versioned key that isolates every permission or identity scope."""
    if domain not in CACHE_TTLS:
        raise ValueError(f"Caching is not enabled for domain {domain!r}.")
    if not permission_scope.strip():
        raise ValueError("A permission scope is required for every cached value.")
    if not resource.strip():
        raise ValueError("A resource key is required for every cached value.")
    return f"{CACHE_PREFIX}:{domain}:{_digest(permission_scope)}:{_digest(resource)}"


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {"__sunpower_type__": "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {"__sunpower_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__sunpower_type__": "date", "value": value.isoformat()}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    raise TypeError(f"Unsupported cache value type: {type(value).__name__}")


def _json_object_hook(value: dict[str, Any]) -> Any:
    tagged = value.get("__sunpower_type__")
    raw = value.get("value")
    if tagged == "decimal":
        return Decimal(raw)
    if tagged == "datetime":
        return datetime.fromisoformat(raw)
    if tagged == "date":
        return date.fromisoformat(raw)
    return value


def _log(event: str, domain: str, **fields: Any) -> None:
    logger.info(
        "cache_%s",
        event,
        extra={"cache_event": event, "cache_domain": domain, **fields},
    )


def get_or_load(
    domain: str,
    permission_scope: str,
    resource: str,
    loader: Callable[[], T],
    *,
    client: Any | None = None,
) -> T:
    """Return a cached value or load it from the source of truth and cache it."""
    key = cache_key(domain, permission_scope, resource)
    redis_client = client if client is not None else get_redis_client()
    fallback_reason = "cache_miss"
    try:
        cached = redis_client.get(key)
        if cached is not None:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            try:
                value = json.loads(cached, object_hook=_json_object_hook)
            except (TypeError, ValueError):
                _log("error", domain, reason="invalid_cached_json")
                fallback_reason = "invalid_cached_json"
            else:
                _log("hit", domain)
                return value
        else:
            _log("miss", domain)
    except RedisError as exc:
        _log("error", domain, reason=type(exc).__name__)
        fallback_reason = "redis_unavailable"

    # Database exceptions intentionally propagate. Redis failures never mask the
    # authoritative loader or turn a successful business read into an error.
    _log("database_fallback", domain, reason=fallback_reason)
    value = loader()
    try:
        payload = json.dumps(value, default=_json_default, separators=(",", ":"))
        redis_client.set(key, payload, ex=CACHE_TTLS[domain])
    except (RedisError, TypeError, ValueError) as exc:
        _log("error", domain, reason=type(exc).__name__)
    return value


def invalidate(domain: str, *, client: Any | None = None) -> int:
    """Invalidate all permission scopes for one domain after a committed write."""
    if domain not in CACHE_TTLS:
        return 0
    redis_client = client if client is not None else get_redis_client()
    pattern = f"{CACHE_PREFIX}:{domain}:*"
    try:
        keys = list(redis_client.scan_iter(match=pattern, count=200))
        removed = 0
        for offset in range(0, len(keys), 200):
            removed += int(redis_client.delete(*keys[offset : offset + 200]))
        _log("invalidation", domain, removed=removed)
        return removed
    except RedisError as exc:
        _log("error", domain, reason=type(exc).__name__)
        return 0
