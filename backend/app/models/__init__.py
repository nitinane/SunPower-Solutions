"""SQLAlchemy model registry imported by Alembic autogenerate.

Import each domain module here so all mapped tables are registered on Base.metadata.
"""

from app.db.base import Base
from app.models import (
    auth,
    catalog,
    customers,
    dashboard,
    dispatch,
    enquiries,
    files,
    installations,
    inventory,
    invoices,
    orders,
    payments,
    quotes,
    service_tickets,
    subsidies,
    surveys,
    technician_pay,
    users,
    warranties,
)

__all__ = [
    "Base",
    "auth",
    "catalog",
    "customers",
    "dashboard",
    "dispatch",
    "enquiries",
    "files",
    "installations",
    "inventory",
    "invoices",
    "orders",
    "payments",
    "quotes",
    "service_tickets",
    "subsidies",
    "surveys",
    "technician_pay",
    "users",
    "warranties",
]
