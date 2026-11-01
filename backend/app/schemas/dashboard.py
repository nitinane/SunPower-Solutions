"""Database-backed dashboard and financial report response."""

from decimal import Decimal

from pydantic import BaseModel


class ReportRead(BaseModel):
    customer_count: int
    order_count: int
    total_revenue: Decimal
    outstanding_payments: Decimal
    installation_count: int
    completed_jobs: int
    unfinished_jobs: int
    open_support_tickets: int
    profit_per_job: dict[int, Decimal]
