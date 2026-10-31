from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    code = "application_error"
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFound(AppError):
    code = "not_found"
    status_code = 404


class Conflict(AppError):
    code = "conflict"
    status_code = 409


class Forbidden(AppError):
    code = "forbidden"
    status_code = 403


class BusinessRuleViolation(AppError):
    code = "business_rule_violation"
    status_code = 422


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}}
    )
