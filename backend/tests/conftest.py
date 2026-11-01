"""Tests run against their own database: `<db name>_test` on the same Postgres.

The URL is switched before anything imports app.db.session, so the app engine,
SessionLocal and Alembic all point at the test database. The dev database is never touched.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import settings

_url = make_url(settings.database_url)
if not _url.database.endswith("_test"):
    _url = _url.set(database=f"{_url.database}_test")
TEST_DATABASE_URL = _url.render_as_string(hide_password=False)
settings.database_url = TEST_DATABASE_URL

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]


def _create_database() -> None:
    admin = create_engine(_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": _url.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{_url.database}"'))
    admin.dispose()


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, "head")


def _reset_and_seed() -> None:
    from app.db.session import SessionLocal, engine
    from scripts.seed import DEV_DEFAULT_PASSWORD, seed_catalog, seed_stock, seed_users

    with engine.begin() as conn:
        tables = conn.scalars(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "AND tablename <> 'alembic_version'"
            )
        ).all()
        if tables:
            names = ", ".join(f'"{name}"' for name in tables)
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        seed_users(db, DEV_DEFAULT_PASSWORD)
        seed_catalog(db)
        seed_stock(db)
        db.commit()


@pytest.fixture(scope="session", autouse=True)
def test_storage(tmp_path_factory):
    original_storage_dir = settings.storage_dir
    settings.storage_dir = str(tmp_path_factory.mktemp("storage"))
    yield
    settings.storage_dir = original_storage_dir


@pytest.fixture(scope="session", autouse=True)
def test_database():
    assert make_url(settings.database_url).database.endswith("_test")
    _create_database()
    _migrate()
    _reset_and_seed()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
