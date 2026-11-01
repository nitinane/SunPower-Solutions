from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.customers import Customer
from app.models.orders import Order
from scripts.seed import (
    ensure_evidence_assets,
    require_demo_database,
    seed_dataset,
    table_counts,
    verify_dataset,
    verify_evidence_assets,
)


@pytest.fixture
def seed_test_engine():
    database_url = os.environ.get("SUNPOWER_DEMO_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set SUNPOWER_DEMO_TEST_DATABASE_URL to the dedicated sunpower_demo database.")
    if make_url(database_url).database != "sunpower_demo":
        pytest.fail("Demo seed integration tests only run against sunpower_demo.")

    schema = f"seed_test_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(database_url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def test_generates_exact_counts_and_reconciles_all_domains(seed_test_engine) -> None:
    with Session(seed_test_engine) as session, session.begin():
        assert seed_dataset(session, customers=300, orders=300, seed=42)
        counts = verify_dataset(session, customers=300, orders=300, print_report=False)

    assert counts["customers"] == 300
    assert counts["orders"] == 300
    assert all(count > 0 for count in counts.values())
    assert counts["support_tickets"] == 60


def test_generation_is_deterministic_and_idempotent(seed_test_engine) -> None:
    with Session(seed_test_engine) as session, session.begin():
        assert seed_dataset(session, customers=6, orders=6, seed=42)
        first = session.execute(
            select(Customer.email, Customer.full_name).order_by(Customer.email)
        ).all()
        first_orders = session.execute(
            select(Order.order_number, Order.status).order_by(Order.order_number)
        ).all()

    with Session(seed_test_engine) as session, session.begin():
        assert not seed_dataset(session, customers=6, orders=6, seed=42)
        counts = table_counts(session)

    with Session(seed_test_engine) as session, session.begin():
        assert seed_dataset(session, customers=6, orders=6, seed=42, reset=True)
        second = session.execute(
            select(Customer.email, Customer.full_name).order_by(Customer.email)
        ).all()
        second_orders = session.execute(
            select(Order.order_number, Order.status).order_by(Order.order_number)
        ).all()

    assert first == second
    assert first_orders == second_orders
    assert counts["customers"] == counts["orders"] == 6


def test_database_guard_refuses_non_demo_database() -> None:
    class OtherDatabaseResult:
        @staticmethod
        def scalar_one() -> str:
            return "sunpower"

    class OtherDatabaseSession:
        @staticmethod
        def execute(_statement):
            return OtherDatabaseResult()

    with pytest.raises(RuntimeError, match="only 'sunpower_demo' is allowed"):
        require_demo_database(OtherDatabaseSession())


def test_generation_rolls_back_with_the_callers_transaction(seed_test_engine) -> None:
    with pytest.raises(RuntimeError, match="forced rollback"):
        with Session(seed_test_engine) as session, session.begin():
            seed_dataset(session, customers=6, orders=6, seed=42)
            raise RuntimeError("forced rollback")

    with Session(seed_test_engine) as session:
        assert session.scalar(select(Customer.id).limit(1)) is None
        assert session.scalar(select(Order.id).limit(1)) is None


def test_evidence_records_have_readable_demo_assets(seed_test_engine, tmp_path) -> None:
    with Session(seed_test_engine) as session, session.begin():
        seed_dataset(session, customers=6, orders=6, seed=42)
        created_files = ensure_evidence_assets(session, tmp_path)
        verify_evidence_assets(session, tmp_path)

    assert len(created_files) == 12
    assert all(len(path.name.split("/")) == 1 for path in created_files)
    assert any(
        path.suffix == ".png" and path.read_bytes().startswith(b"\x89PNG") for path in created_files
    )
    assert any(
        path.suffix == ".pdf" and path.read_bytes().startswith(b"%PDF") for path in created_files
    )
