"""Exercise every private route without a session, including invalid bodies."""

import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth
from app.core.config import Settings, settings
from app.main import create_app

PUBLIC = {
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/enquiries/public"),
    ("GET", "/api/v1/public/dashboard/{token}"),
    ("GET", "/api/health"), ("GET", "/api/health/ready"),
    ("GET", "/health"), ("GET", "/health/ready"),
}
PRIVATE = [
    (method.upper(), path)
    for path, operations in create_app().openapi()["paths"].items()
    for method in operations
    if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    and (method.upper(), path) not in PUBLIC
]


def test_route_inventory_is_not_empty():
    assert len(PRIVATE) >= 40


@pytest.mark.parametrize("method,path", PRIVATE)
def test_private_route_requires_cookie(client, method, path):
    url = re.sub(r"\{[^}]+\}", "1", path)
    kwargs = {"json": {}} if method in {"POST", "PUT", "PATCH"} else {}
    assert client.request(method, url, **kwargs).status_code == 401


@pytest.mark.parametrize("environment,secure", [("production", True), ("development", False)])
def test_session_cookie_flags(client, monkeypatch, environment, secure):
    from datetime import UTC, datetime

    monkeypatch.setattr(settings, "env", environment)
    monkeypatch.setattr(auth.auth_service, "login", lambda *a, **kw: SimpleNamespace(
        token="test-token", expires_at=datetime.now(UTC),
        user=SimpleNamespace(id=1, full_name="Test", email="test@example.com", role="office"),
    ))
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com", "password": "test-password",
    })
    assert response.status_code == 200, response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/;" in cookie
    assert ("; secure" in cookie) == secure


def test_production_cors(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings(cors_origins="*").cors_origin_list == []


def test_readiness(client):
    assert client.get("/health/ready").status_code == 200


def test_readiness_dependency_failure(client, monkeypatch):
    monkeypatch.setattr("app.main.SessionLocal", lambda: (_ for _ in ()).throw(
        RuntimeError("private database details")
    ))
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert "private database details" not in response.text


def test_unexpected_error_hides_details():
    app = create_app()

    @app.get("/test-crash")
    def crash():
        raise RuntimeError("SELECT secret FROM private_table")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-crash", headers={"X-Request-ID": "safe-id"})
    assert response.status_code == 500
    assert "SELECT" not in response.text
    assert response.json()["error"]["request_id"] == "safe-id"
