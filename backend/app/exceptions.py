"""
Business errors raised by services.

Pure Python on purpose: no FastAPI import here, so services stay framework-free.
app/api/errors.py turns these into HTTP responses with one JSON shape:
{"error": {"code": "...", "message": "...", "fields": {...}}}
"""


class AppError(Exception):
    code = "application_error"
    status_code = 400

    def __init__(self, message: str, *, fields: dict[str, str] | None = None) -> None:
        self.message = message
        self.fields = fields or {}
        super().__init__(message)


class ValidationFailed(AppError):
    """Input is wrong. `fields` says which field and why. Frontend shows it under the input."""
    code = "validation_error"
    status_code = 422


class Unauthorized(AppError):
    """Not logged in, or the session expired."""
    code = "unauthorized"
    status_code = 401


class Forbidden(AppError):
    """Logged in, but this role may not do this."""
    code = "forbidden"
    status_code = 403


class NotFound(AppError):
    """The record does not exist (or the user may not see it)."""
    code = "not_found"
    status_code = 404


class Conflict(AppError):
    """Duplicate or clashing data, e.g. serial already dispatched, crew double-booked."""
    code = "conflict"
    status_code = 409


class BusinessRuleViolation(AppError):
    """A workflow rule blocks the action, e.g. quote before survey approval."""
    code = "business_rule_violation"
    status_code = 409