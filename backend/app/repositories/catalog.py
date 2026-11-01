"""Product and solar package queries. No commits and no business rules here."""

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import PackageType
from app.models.catalog import PackageComponent, Product, SolarPackage


def get_product_by_sku(db: Session, sku: str) -> Product | None:
    return db.scalars(select(Product).where(Product.sku == sku)).first()


def create_product(db: Session, data: dict[str, Any]) -> Product:
    product = Product(**data)
    db.add(product)
    db.flush()
    return product


def count_products(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Product)) or 0


def get_package(db: Session, package_id: int) -> SolarPackage | None:
    return db.get(SolarPackage, package_id)


def find_package(db: Session, package_type: str, kw: Decimal) -> SolarPackage | None:
    stmt = select(SolarPackage).where(
        SolarPackage.package_type == package_type, SolarPackage.system_capacity_kw == kw
    )
    return db.scalars(stmt.order_by(SolarPackage.id).limit(1)).first()


def create_package(db: Session, data: dict[str, Any]) -> SolarPackage:
    package = SolarPackage(**data)
    db.add(package)
    db.flush()
    return package


def add_component(db: Session, package_id: int, product_id: int, qty: Decimal) -> None:
    db.add(PackageComponent(package_id=package_id, product_id=product_id, quantity=qty))
    db.flush()


def count_packages(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SolarPackage)) or 0


def list_active_packages(
    db: Session, *, package_type: PackageType | None = None, kw: Decimal | None = None
) -> list[SolarPackage]:
    stmt = select(SolarPackage).where(SolarPackage.is_active.is_(True))
    if package_type:
        stmt = stmt.where(SolarPackage.package_type == package_type)
    if kw is not None:
        stmt = stmt.where(SolarPackage.system_capacity_kw == kw)
    return list(
        db.scalars(stmt.order_by(SolarPackage.package_type, SolarPackage.system_capacity_kw))
    )


def list_components(
    db: Session, package_ids: list[int]
) -> list[tuple[PackageComponent, Product]]:
    """Component lines with their products, in a stable order (component id)."""
    if not package_ids:
        return []
    stmt = (
        select(PackageComponent, Product)
        .join(Product, Product.id == PackageComponent.product_id)
        .where(PackageComponent.package_id.in_(package_ids))
        .order_by(PackageComponent.package_id, PackageComponent.id)
    )
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def list_products(db: Session, *, search, requires_serial, limit, offset):
    from sqlalchemy import case, or_

    from app.models.inventory import Inventory, SerializedUnit

    serial_stock = (
        select(func.count(SerializedUnit.id))
        .where(SerializedUnit.product_id == Product.id, SerializedUnit.status == "in_stock")
        .correlate(Product).scalar_subquery()
    )
    stock = case((Product.tracks_serial, serial_stock),
                 else_=func.coalesce(Inventory.quantity_on_hand, 0)).label("in_stock")
    stmt = select(Product, stock).outerjoin(Inventory, Inventory.product_id == Product.id)
    if search:
        pattern = "%" + search.replace("/", "//").replace("%", "/%").replace("_", "/_") + "%"
        stmt = stmt.where(or_(Product.sku.ilike(pattern, escape="/"),
                              Product.name.ilike(pattern, escape="/")))
    if requires_serial is not None:
        stmt = stmt.where(Product.tracks_serial == requires_serial)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    return db.execute(stmt.order_by(Product.id).limit(limit).offset(offset)).all(), total
