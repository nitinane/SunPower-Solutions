"""
Demo data for local runs and the hackathon demo. Safe to run many times (skips what exists).

Run:  docker compose exec api python -m scripts.seed
      (or locally from backend/:  python -m scripts.seed)

Password for every demo user comes from SEED_PASSWORD (default only outside production).
"""

import math
import os
import sys
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.enums import PackageType, ProductCategory, SerialUnitStatus, UserRole
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.catalog import Product
from app.models.inventory import Inventory, SerializedUnit
from app.repositories import catalog as catalog_repo
from app.repositories import users as user_repo

DEV_DEFAULT_PASSWORD = "SunPower@2026"

DEMO_USERS = [
    {"full_name": "Admin User", "email": "admin@sunpower.in", "role": UserRole.ADMIN},
    {"full_name": "Divya Director", "email": "director@sunpower.in", "role": UserRole.DIRECTOR},
    {"full_name": "Asha Office", "email": "office@sunpower.in", "role": UserRole.OFFICE},
    {"full_name": "Sameer Surveyor", "email": "surveyor@sunpower.in", "role": UserRole.SURVEYOR},
    {"full_name": "Wasim Warehouse", "email": "warehouse@sunpower.in", "role": UserRole.WAREHOUSE},
    {"full_name": "Sunita Support", "email": "support@sunpower.in", "role": UserRole.SUPPORT},
    {
        "full_name": "Raju Technician",
        "email": "tech1@sunpower.in",
        "role": UserRole.TECHNICIAN,
        "hourly_rate": Decimal("250.00"),
    },
    {
        "full_name": "Kiran Technician",
        "email": "tech2@sunpower.in",
        "role": UserRole.TECHNICIAN,
        "hourly_rate": Decimal("250.00"),
    },
]


def _seed_password() -> str:
    password = os.environ.get("SEED_PASSWORD")
    if password:
        return password
    if settings.env.lower() == "production":
        sys.exit("Refusing to seed production without SEED_PASSWORD")
    return DEV_DEFAULT_PASSWORD


def seed_users(db, password: str) -> int:
    """Create missing demo users. Returns how many were created."""
    password_hash = hash_password(password)
    created = 0
    for spec in DEMO_USERS:
        if user_repo.get_by_email(db, spec["email"]) is None:
            user_repo.create(db, {**spec, "password_hash": password_hash, "is_active": True})
            created += 1
    return created


# sku, name, category, cost, sale, gst %, warranty months, tracks serial
CATALOG_PRODUCTS = [
    ("PNL-540", "Mono PERC solar panel 540 W", ProductCategory.PANEL,
     11500, 14000, 12, 240, False),
    ("CC-MPPT-40", "MPPT battery charge controller 40 A", ProductCategory.CHARGE_CONTROLLER,
     3200, 4200, 12, 24, True),
    ("BAT-150AH", "Tubular battery 150 Ah", ProductCategory.BATTERY, 11000, 13500, 12, 24, True),
    ("STD-GI", "GI mounting stand (per panel)", ProductCategory.STAND, 1300, 1800, 12, 120, False),
    ("CON-MC4", "MC4 connector pair", ProductCategory.CONNECTOR, 60, 120, 12, 12, False),
    ("WIRE-DC4", "DC solar cable 4 sq mm (per metre)", ProductCategory.WIRE, 45, 70, 12, 12, False),
    ("WIRE-AC6", "AC cable 6 sq mm (per metre)", ProductCategory.WIRE, 55, 85, 12, 12, False),
    ("BOX-ACDB", "AC distribution box", ProductCategory.WIRING_BOX, 1400, 2100, 12, 12, False),
    ("BOX-DCDB", "DC distribution box", ProductCategory.WIRING_BOX, 1600, 2400, 12, 12, False),
    ("SW-MCB", "MCB isolator switch", ProductCategory.SWITCH, 350, 550, 12, 12, False),
    ("EARTH-KIT", "Earthing kit with chemical rod", ProductCategory.EARTHING,
     1800, 2600, 12, 12, False),
    ("EARTH-LA", "Lightning arrester", ProductCategory.EARTHING, 1500, 2200, 12, 12, False),
    ("SVC-INSTALL", "Installation and testing (per kW)", ProductCategory.SERVICE,
     2500, 4500, 18, 0, False),
] + [
    (f"INV-{kw}K", f"Solar inverter {kw} kW", ProductCategory.INVERTER,
     9000 + 6000 * kw, 12000 + 7500 * kw, 12, 24, True)
    for kw in range(1, 6)
]

PACKAGE_NAMES = {
    PackageType.ON_GRID: "{kw} kW On-grid system",
    PackageType.OFF_GRID: "{kw} kW Off-grid system",
    PackageType.PANEL_SET: "{kw} kW Panel set",
}


def package_components(package_type: PackageType, kw: int) -> list[tuple[str, int]]:
    """(sku, qty) lines for one package template."""
    panels = math.ceil(kw * 1000 / 540)
    lines = [("PNL-540", panels), ("CON-MC4", panels), ("WIRE-DC4", 20)]
    if package_type == PackageType.PANEL_SET:
        return lines
    lines += [
        (f"INV-{kw}K", 1),
        ("CC-MPPT-40", 1),
        ("STD-GI", panels),
        ("WIRE-AC6", 15),
        ("BOX-ACDB", 1),
        ("BOX-DCDB", 1),
        ("SW-MCB", 2),
        ("EARTH-KIT", 1),
        ("EARTH-LA", 1),
    ]
    if package_type == PackageType.OFF_GRID:
        lines.append(("BAT-150AH", kw))
    return lines


def seed_catalog(db) -> tuple[int, int]:
    """Create missing products and package templates. Returns (products, packages) created."""
    products_created = 0
    for sku, name, category, cost, sale, gst, warranty, serial in CATALOG_PRODUCTS:
        if catalog_repo.get_product_by_sku(db, sku) is None:
            catalog_repo.create_product(
                db,
                {
                    "sku": sku,
                    "name": name,
                    "category": category,
                    "cost_price": Decimal(cost),
                    "sale_price": Decimal(sale),
                    "gst_rate": Decimal(gst),
                    "warranty_months": warranty,
                    "tracks_serial": serial,
                    "is_active": True,
                },
            )
            products_created += 1

    packages_created = 0
    for package_type, name_pattern in PACKAGE_NAMES.items():
        for kw in range(1, 6):
            if catalog_repo.find_package(db, package_type, Decimal(kw)) is not None:
                continue
            lines = [
                (catalog_repo.get_product_by_sku(db, sku), Decimal(qty))
                for sku, qty in package_components(package_type, kw)
            ]
            package = catalog_repo.create_package(
                db,
                {
                    "name": name_pattern.format(kw=kw),
                    "package_type": package_type,
                    "system_capacity_kw": Decimal(kw),
                    "base_price": sum((p.sale_price * qty for p, qty in lines), Decimal("0")),
                    "is_active": True,
                },
            )
            for product, qty in lines:
                catalog_repo.add_component(db, package.id, product.id, qty)
            packages_created += 1
    return products_created, packages_created


def seed_stock(db) -> None:
    """Insert missing demo stock only; never replenish consumed stock or reset serial status."""
    for product in db.scalars(select(Product).order_by(Product.id)):
        if product.category == ProductCategory.SERVICE:
            continue
        if product.tracks_serial:
            for number in range(1, 11):
                db.execute(insert(SerializedUnit).values(
                    product_id=product.id, serial_number=f"{product.sku}-{number:04d}",
                    status=SerialUnitStatus.IN_STOCK,
                ).on_conflict_do_nothing())
        else:
            quantity = 1000 if product.category == ProductCategory.PANEL else (
                2000 if product.category == ProductCategory.WIRE else 500
            )
            db.execute(insert(Inventory).values(
                product_id=product.id, quantity_on_hand=Decimal(quantity),
                quantity_reserved=Decimal("0"),
            ).on_conflict_do_nothing())
    db.flush()


def main() -> None:
    password = _seed_password()
    with SessionLocal() as db:
        created = seed_users(db, password)
        products, packages = seed_catalog(db)
        seed_stock(db)
        db.commit()
        total_products = catalog_repo.count_products(db)
        total_packages = catalog_repo.count_packages(db)
    print(f"Users: {created} created, {len(DEMO_USERS) - created} already existed")
    print(f"Products: {products} created, {total_products} total")
    print(f"Packages: {packages} created, {total_packages} total")


if __name__ == "__main__":
    main()
