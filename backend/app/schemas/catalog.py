"""Solar package templates with their parts list and a price preview."""

from decimal import Decimal

from pydantic import BaseModel

from app.core.enums import PackageType, ProductCategory


class PriceLine(BaseModel):
    """One parts-list line. line_total = qty x unit_price (before GST); gst_amount is on top."""

    product_id: int
    sku: str
    name: str
    category: ProductCategory | None = None
    qty: Decimal
    unit_price: Decimal
    gst_percent: Decimal
    line_total: Decimal
    gst_amount: Decimal


class PackageRead(BaseModel):
    id: int
    name: str
    package_type: PackageType
    kw: Decimal
    is_active: bool
    components: list[PriceLine]
    subtotal: Decimal
    gst: Decimal
    total: Decimal
