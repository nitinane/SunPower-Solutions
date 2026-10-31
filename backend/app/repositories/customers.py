"""Customers repositorie stub. TODO: implement with the owning team."""
"""Customer and site queries. No commits and no business rules here."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customers import Customer, Site


def get_by_id(db: Session, customer_id: int) -> Customer | None:
    return db.get(Customer, customer_id)


def get_by_phone(db: Session, phone_e164: str) -> Customer | None:
    """Oldest customer with this phone (phone is our customer identity)."""
    stmt = (
        select(Customer)
        .where(Customer.phone_e164 == phone_e164)
        .order_by(Customer.id)
        .limit(1)
    )
    return db.scalars(stmt).first()


def create(db: Session, data: dict[str, Any]) -> Customer:
    customer = Customer(**data)
    db.add(customer)
    db.flush()
    return customer


def find_site(db: Session, customer_id: int, address_line1: str, pincode: str) -> Site | None:
    """Same customer + same address (ignoring case and outer spaces) + same PIN = same roof."""
    stmt = (
        select(Site)
        .where(
            Site.customer_id == customer_id,
            func.lower(func.btrim(Site.address_line1)) == address_line1.strip().lower(),
            Site.pincode == pincode,
        )
        .order_by(Site.id)
        .limit(1)
    )
    return db.scalars(stmt).first()


def create_site(db: Session, data: dict[str, Any]) -> Site:
    site = Site(**data)
    db.add(site)
    db.flush()
    return site


def list_sites(db: Session, customer_id: int) -> list[Site]:
    return list(db.scalars(select(Site).where(Site.customer_id == customer_id).order_by(Site.id)))