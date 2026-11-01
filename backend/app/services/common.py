"""Small helpers shared by every service."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RequestMeta:
    """Where a request came from; saved in audit_log next to each change."""

    request_id: str | None = None
    ip_address: str | None = None