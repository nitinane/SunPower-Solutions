from __future__ import annotations

import os
import time
import uuid
from decimal import Decimal

import pytest
import redis
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core import cache_invalidation as _cache_invalidation  # noqa: F401
from app.core.cache import CACHE_TTLS, cache_key, get_or_load, get_redis_client
from app.models.catalog import Product


@pytest.fixture(scope="module")
def cache_test_engine():
    database_url = os.environ.get("SUNPOWER_CACHE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "Set SUNPOWER_CACHE_TEST_DATABASE_URL to the disposable sunpower_demo database."
        )
    parsed_url = make_url(database_url)
    if parsed_url.database != "sunpower_demo":
        pytest.fail("Cache integration tests require the dedicated sunpower_demo database.")

    schema_name = f"cache_test_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema_name}"')

    test_engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema_name}"},
    )
    try:
        Product.__table__.create(test_engine)
        yield test_engine
    finally:
        test_engine.dispose()
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA "{schema_name}" CASCADE')
        admin_engine.dispose()


@pytest.fixture
def redis_client():
    client = get_redis_client()
    client.ping()
    yield client
    client.close()


def add_product(session: Session, sku: str, name: str) -> int:
    product = Product(
        sku=sku,
        name=name,
        category="panel",
        cost_price=Decimal("10.50"),
        sale_price=Decimal("14.25"),
        gst_rate=Decimal("5.00"),
        warranty_months=120,
        tracks_serial=False,
        is_active=True,
    )
    session.add(product)
    session.commit()
    return product.id


def load_product(session: Session, product_id: int) -> dict[str, object]:
    product = session.scalar(select(Product).where(Product.id == product_id))
    assert product is not None
    return {
        "sku": product.sku,
        "name": product.name,
        "price": product.sale_price,
        "created_at": product.created_at,
    }


def test_first_request_loads_postgres_second_request_hits_redis(
    cache_test_engine, redis_client, caplog
) -> None:
    sku = f"CACHE-{uuid.uuid4().hex[:12]}"
    with Session(cache_test_engine) as session:
        product_id = add_product(session, sku, "Solar panel")
        resource = f"product:{product_id}"
        key = cache_key("product_catalog", "role:warehouse:user:101", resource)
        redis_client.delete(key)
        loads = 0

        def loader() -> dict[str, object]:
            nonlocal loads
            loads += 1
            return load_product(session, product_id)

        first = get_or_load(
            "product_catalog", "role:warehouse:user:101", resource, loader, client=redis_client
        )
        second = get_or_load(
            "product_catalog", "role:warehouse:user:101", resource, loader, client=redis_client
        )

        assert loads == 1
        assert first == second
        assert first["price"] == Decimal("14.25")
        assert first["created_at"].tzinfo is not None
        assert 0 < redis_client.ttl(key) <= CACHE_TTLS["product_catalog"]
        events = [record.cache_event for record in caplog.records if hasattr(record, "cache_event")]
        assert "miss" in events
        assert "database_fallback" in events
        assert "hit" in events


def test_expired_key_uses_postgres_again(cache_test_engine, redis_client) -> None:
    sku = f"CACHE-{uuid.uuid4().hex[:12]}"
    with Session(cache_test_engine) as session:
        product_id = add_product(session, sku, "Expiring panel")
        resource = f"product:{product_id}"
        key = cache_key("product_catalog", "role:office:user:102", resource)
        redis_client.delete(key)
        loads = 0

        def loader() -> dict[str, object]:
            nonlocal loads
            loads += 1
            return load_product(session, product_id)

        get_or_load(
            "product_catalog", "role:office:user:102", resource, loader, client=redis_client
        )
        redis_client.expire(key, 1)
        time.sleep(1.1)
        get_or_load(
            "product_catalog", "role:office:user:102", resource, loader, client=redis_client
        )
        assert loads == 2


def test_committed_catalog_update_invalidates_cache(cache_test_engine, redis_client) -> None:
    sku = f"CACHE-{uuid.uuid4().hex[:12]}"
    with Session(cache_test_engine) as session:
        product_id = add_product(session, sku, "Before update")
        scope = "role:director:user:103"
        resource = f"product:{product_id}"
        key = cache_key("product_catalog", scope, resource)
        redis_client.delete(key)

        get_or_load(
            "product_catalog",
            scope,
            resource,
            lambda: load_product(session, product_id),
            client=redis_client,
        )
        assert redis_client.exists(key)

        product = session.get(Product, product_id)
        assert product is not None
        product.name = "After update"
        session.commit()
        assert not redis_client.exists(key)

        fresh = get_or_load(
            "product_catalog",
            scope,
            resource,
            lambda: load_product(session, product_id),
            client=redis_client,
        )
        assert fresh["name"] == "After update"


def test_permission_scopes_do_not_share_cached_values(redis_client) -> None:
    resource = f"summary:{uuid.uuid4().hex}"
    director = get_or_load(
        "dashboard_summary",
        "role:director:user:201",
        resource,
        lambda: {"visible": "finance"},
        client=redis_client,
    )
    technician = get_or_load(
        "dashboard_summary",
        "role:technician:user:202",
        resource,
        lambda: {"visible": "jobs"},
        client=redis_client,
    )
    assert director == {"visible": "finance"}
    assert technician == {"visible": "jobs"}
    assert cache_key("dashboard_summary", "role:director:user:201", resource) != cache_key(
        "dashboard_summary", "role:technician:user:202", resource
    )


def test_redis_outage_falls_back_to_loader() -> None:
    class UnavailableRedis:
        def get(self, _key: str) -> None:
            raise redis.ConnectionError("offline")

        def set(self, *_args: object, **_kwargs: object) -> None:
            raise redis.ConnectionError("offline")

    loaded: list[bool] = []
    value = get_or_load(
        "enum_metadata",
        "public",
        f"metadata:{uuid.uuid4().hex}",
        lambda: loaded.append(True) or {"ok": True},
        client=UnavailableRedis(),
    )
    assert loaded == [True]
    assert value == {"ok": True}


def test_sensitive_domains_are_not_cacheable() -> None:
    for domain in ("payments", "inventory", "warranty_eligibility"):
        with pytest.raises(ValueError, match="Caching is not enabled"):
            cache_key(domain, "role:director:user:1", "summary")


def test_permission_scope_is_mandatory() -> None:
    with pytest.raises(ValueError, match="permission scope is required"):
        cache_key("dashboard_summary", "", "summary")
