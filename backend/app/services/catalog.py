"""
Catalog: solar package templates (on-grid / off-grid / panel set, 1-5 kW) with a price preview.

Money rule (shared with quotes): per line, line_total = qty x unit_price and
gst_amount = line_total x gst% / 100, each quantized to 0.01 (ROUND_HALF_UP).
Subtotal, GST and total are sums of the quantized lines.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.enums import PackageType
from app.repositories import catalog as catalog_repo
from app.schemas.catalog import PackageRead, PriceLine

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def price_line(
    *,
    product_id: int,
    sku: str,
    name: str,
    qty: Decimal,
    unit_price: Decimal,
    gst_percent: Decimal,
    category: str | None = None,
) -> PriceLine:
    line_total = money(qty * unit_price)
    return PriceLine(
        product_id=product_id,
        sku=sku,
        name=name,
        category=category,
        qty=qty,
        unit_price=unit_price,
        gst_percent=gst_percent,
        line_total=line_total,
        gst_amount=money(line_total * gst_percent / Decimal(100)),
    )


def totals(lines: list[PriceLine]) -> tuple[Decimal, Decimal, Decimal]:
    """(subtotal, gst, total) as sums of the already-quantized lines."""
    subtotal = sum((line.line_total for line in lines), Decimal("0.00"))
    gst = sum((line.gst_amount for line in lines), Decimal("0.00"))
    return money(subtotal), money(gst), money(subtotal + gst)


def list_packages(
    db: Session, *, package_type: PackageType | None = None, kw: Decimal | None = None
) -> list[PackageRead]:
    """Active packages with today's prices (a preview; quotes freeze their own snapshot)."""
    packages = catalog_repo.list_active_packages(db, package_type=package_type, kw=kw)
    lines_by_package: dict[int, list[PriceLine]] = {p.id: [] for p in packages}
    for component, product in catalog_repo.list_components(db, list(lines_by_package)):
        lines_by_package[component.package_id].append(
            price_line(
                product_id=product.id,
                sku=product.sku,
                name=product.name,
                category=product.category,
                qty=component.quantity,
                unit_price=product.sale_price,
                gst_percent=product.gst_rate,
            )
        )

    result = []
    for package in packages:
        lines = lines_by_package[package.id]
        subtotal, gst, total = totals(lines)
        result.append(
            PackageRead(
                id=package.id,
                name=package.name,
                package_type=package.package_type,
                kw=package.system_capacity_kw,
                is_active=package.is_active,
                components=lines,
                subtotal=subtotal,
                gst=gst,
                total=total,
            )
        )
    return result
