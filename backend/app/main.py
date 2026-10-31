import logging
import re
import uuid

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Accept a caller's X-Request-ID only if it is short and safe (prevents log injection).
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    application = FastAPI(
        title="SunPower Solutions API",
        version="0.1.0",
        docs_url="/api/docs",              # Nginx only forwards /api/*, so docs live there
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )

    register_exception_handlers(application)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if REQUEST_ID_PATTERN.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.get("/health")
    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready")
    @application.get("/api/health/ready")
    def readiness() -> dict[str, str]:
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
            with redis.Redis.from_url(
                settings.redis_url, socket_connect_timeout=2, socket_timeout=2
            ) as cache:
                cache.ping()
        except Exception as exc:
            logger.exception("Readiness check failed")
            raise HTTPException(status_code=503, detail="A dependency is unavailable") from exc
        return {"status": "ready", "database": "ok", "redis": "ok"}

    application.include_router(api_router)
    return application


app = create_app()
