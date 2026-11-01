"""Inventory and dispatch read schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class InventoryProductRead(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
    cost_price: Decimal
    sale_price: Decimal
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    quantity_available: Decimal
    low_stock: bool


class StockMovementRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    order_id: int | None
    quantity_delta: Decimal
    reason: str
    note: str | None
    created_at: datetime


class SerializedUnitRead(BaseModel):
    id: int
    product_id: int
    product_name: str
    serial_number: str
    status: str
    received_at: datetime | None


class DispatchItemRead(BaseModel):
    id: int
    order_item_id: int
    product_id: int
    product_name: str
    quantity: Decimal
    serialized_unit_id: int | None


class DispatchRead(BaseModel):
    id: int
    order_id: int
    dispatch_number: str
    status: str
    dispatched_at: datetime | None
    delivered_at: datetime | None
    items: list[DispatchItemRead]


class DispatchListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    dispatch_number: str
    status: str
    dispatched_at: datetime | None
