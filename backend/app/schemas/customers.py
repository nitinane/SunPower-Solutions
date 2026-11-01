"""Request and response schemas for customers and installation sites."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CustomerListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    full_name: str
    phone_e164: str
    email: str | None
    created_at: datetime
    site_count: int
    order_count: int


class CustomerEnquirySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    status: str
    source: str
    contact_name: str
    created_at: datetime


class CustomerOrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    order_number: str
    status: str
    created_at: datetime


class CustomerInstallationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    order_id: int
    site_id: int
    status: str
    scheduled_at: datetime | None
    completed_at: datetime | None


class CustomerWarrantySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int
    order_id: int
    product_id: int
    start_date: date
    end_date: date
    voided_at: datetime | None


class SiteRead(BaseModel):
    """An installation site belonging to a customer."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    customer_id: int
    site_name: str | None
    address_line1: str
    address_line2: str | None
    locality: str | None
    city: str
    state: str
    pincode: str
    latitude: Decimal | None
    longitude: Decimal | None
    electricity_consumer_number: str | None
    created_at: datetime
    updated_at: datetime


class CustomerRead(BaseModel):
    """Customer details and the sites where their systems may be installed."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    full_name: str
    phone_e164: str
    email: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    sites: list[SiteRead]
    enquiries: list[CustomerEnquirySummary] = []
    orders: list[CustomerOrderSummary] = []
    installations: list[CustomerInstallationSummary] = []
    warranties: list[CustomerWarrantySummary] = []
