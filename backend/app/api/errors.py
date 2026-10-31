"""
Maps every error to the JSON shape the frontend expects:
{"error": {"code": "...", "message": "...", "fields": {"phone": "..."}}}

Registered once in main.py via register_exception_handlers(app).
"""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import AppError

logger = logging.getLogger(__name__)

VALUE_ERROR_PREFIX = "Value error, "
LOCATION_WORDS = {"body", "query", "path", "header", "cookie"}
HTTP_CODES = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}


def error_body(code: str, message: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    """Build the standard error JSON."""
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    return body


def _field_name(loc: Sequence[Any]) -> str:
    """('body', 'phone') -> 'phone';  ('body', 'items', 0, 'qty') -> 'items.0.qty'."""
    parts = [str(part) for part in loc if part not in LOCATION_WORDS]
    return ".".join(parts) or "request"


def _clean_message(message: str) -> str:
    """Drop Pydantic's 'Value error, ' prefix so users see only our sentence."""
    return message.removeprefix(VALUE_ERROR_PREFIX)


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """Our own business errors (NotFound, Conflict, ...)."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.fields),
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic input errors -> 422 with one message per field."""
    fields: dict[str, str] = {}
    for err in exc.errors():
        fields.setdefault(_field_name(err.get("loc", ())), _clean_message(err.get("msg", "Invalid value")))
    return JSONResponse(
        status_code=422,
        content=error_body("validation_error", "Some fields are invalid", fields),
    )


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Framework errors like unknown URL (404) or wrong method (405), same JSON shape."""
    message = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(HTTP_CODES.get(exc.status_code, "http_error"), message),
        headers=getattr(exc, "headers", None),
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Any crash -> log full details on the server, send a safe message (no stack trace)."""
    logger.exception(
        "Unhandled error",
        extra={"request_id": getattr(request.state, "request_id", None), "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content=error_body("internal_error", "Something went wrong. Please try again."),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all handlers to the app. Call once in main.py."""
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)