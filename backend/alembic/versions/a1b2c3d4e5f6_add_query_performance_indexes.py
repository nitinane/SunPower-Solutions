"""add query performance indexes

Revision ID: a1b2c3d4e5f6
Revises: 8e3552287d3a
Create Date: 2026-11-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "8e3552287d3a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_products_category_active", "products", ["category", "is_active"], unique=False
    )
    op.create_index(
        "ix_users_phone",
        "users",
        ["phone"],
        unique=False,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )
    op.create_index("ix_users_role_active", "users", ["role", "is_active"], unique=False)
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False)
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"], unique=False)
    op.create_index(
        "ix_customers_email_lower",
        "customers",
        [sa.literal_column("lower(email)")],
        unique=False,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index("ix_customers_phone_e164", "customers", ["phone_e164"], unique=False)
    op.create_index(
        "ix_serialized_units_product_status",
        "serialized_units",
        ["product_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_serialized_units_serial_number", "serialized_units", ["serial_number"], unique=False
    )
    op.create_index("ix_sites_customer_id", "sites", ["customer_id"], unique=False)
    op.create_index(
        "ix_sites_electricity_consumer_number",
        "sites",
        ["electricity_consumer_number"],
        unique=False,
    )
    op.create_index("ix_enquiries_phone_e164", "enquiries", ["phone_e164"], unique=False)
    op.create_index(
        "ix_enquiries_status_created_at", "enquiries", ["status", "created_at"], unique=False
    )
    op.create_index("ix_site_surveys_enquiry_id", "site_surveys", ["enquiry_id"], unique=False)
    op.create_index(
        "ix_site_surveys_surveyor_status", "site_surveys", ["surveyor_id", "status"], unique=False
    )
    op.create_index("ix_quotes_enquiry_status", "quotes", ["enquiry_id", "status"], unique=False)
    op.create_index(
        "ix_orders_customer_created_at", "orders", ["customer_id", "created_at"], unique=False
    )
    op.create_index("ix_quote_items_quote_id", "quote_items", ["quote_id"], unique=False)
    op.create_index(
        "ix_dispatches_order_status", "dispatches", ["order_id", "status"], unique=False
    )
    op.create_index(
        "ix_installation_jobs_scheduled_status",
        "installation_jobs",
        ["scheduled_at", "status"],
        unique=False,
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
    op.create_index(
        "ix_stock_movements_product_created",
        "stock_movements",
        ["product_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_subsidy_applications_customer_status",
        "subsidy_applications",
        ["customer_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_dispatch_items_order_item_id", "dispatch_items", ["order_item_id"], unique=False
    )
    op.create_index(
        "ix_installation_evidence_job_type",
        "installation_evidence",
        ["job_id", "evidence_type"],
        unique=False,
    )
    op.create_index(
        "ix_job_technicians_technician_id", "job_technicians", ["technician_id"], unique=False
    )
    op.create_index(
        "ix_technician_payments_technician_status",
        "technician_payments",
        ["technician_id", "status"],
        unique=False,
    )
    op.create_index("ix_warranties_end_date", "warranties", ["end_date"], unique=False)
    op.create_index(
        "ix_support_tickets_customer_status",
        "support_tickets",
        ["customer_id", "status"],
        unique=False,
    )
    op.create_index("ix_support_tickets_site_id", "support_tickets", ["site_id"], unique=False)
    op.create_index("ix_invoices_order_id", "invoices", ["order_id"], unique=False)
    op.create_index("ix_invoices_ticket_id", "invoices", ["ticket_id"], unique=False)
    op.create_index("ix_payments_order_id", "payments", ["order_id"], unique=False)
    op.create_index("ix_payments_ticket_id", "payments", ["ticket_id"], unique=False)
    op.create_index("ix_ticket_charges_ticket_id", "ticket_charges", ["ticket_id"], unique=False)
    op.create_index(
        "ix_ticket_work_logs_ticket_created",
        "ticket_work_logs",
        ["ticket_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_products_category_active", table_name="products")
    op.drop_index(
        "ix_users_phone", table_name="users", postgresql_where=sa.text("phone IS NOT NULL")
    )
    op.drop_index("ix_users_role_active", table_name="users")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index(
        "ix_customers_email_lower",
        table_name="customers",
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.drop_index("ix_customers_phone_e164", table_name="customers")
    op.drop_index("ix_serialized_units_product_status", table_name="serialized_units")
    op.drop_index("ix_serialized_units_serial_number", table_name="serialized_units")
    op.drop_index("ix_sites_customer_id", table_name="sites")
    op.drop_index("ix_sites_electricity_consumer_number", table_name="sites")
    op.drop_index("ix_enquiries_phone_e164", table_name="enquiries")
    op.drop_index("ix_enquiries_status_created_at", table_name="enquiries")
    op.drop_index("ix_site_surveys_enquiry_id", table_name="site_surveys")
    op.drop_index("ix_site_surveys_surveyor_status", table_name="site_surveys")
    op.drop_index("ix_quotes_enquiry_status", table_name="quotes")
    op.drop_index("ix_orders_customer_created_at", table_name="orders")
    op.drop_index("ix_quote_items_quote_id", table_name="quote_items")
    op.drop_index("ix_dispatches_order_status", table_name="dispatches")
    op.drop_index("ix_installation_jobs_scheduled_status", table_name="installation_jobs")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_index("ix_stock_movements_product_created", table_name="stock_movements")
    op.drop_index("ix_subsidy_applications_customer_status", table_name="subsidy_applications")
    op.drop_index("ix_dispatch_items_order_item_id", table_name="dispatch_items")
    op.drop_index("ix_installation_evidence_job_type", table_name="installation_evidence")
    op.drop_index("ix_job_technicians_technician_id", table_name="job_technicians")
    op.drop_index("ix_technician_payments_technician_status", table_name="technician_payments")
    op.drop_index("ix_warranties_end_date", table_name="warranties")
    op.drop_index("ix_support_tickets_customer_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_site_id", table_name="support_tickets")
    op.drop_index("ix_invoices_order_id", table_name="invoices")
    op.drop_index("ix_invoices_ticket_id", table_name="invoices")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_index("ix_payments_ticket_id", table_name="payments")
    op.drop_index("ix_ticket_charges_ticket_id", table_name="ticket_charges")
    op.drop_index("ix_ticket_work_logs_ticket_created", table_name="ticket_work_logs")
    op.drop_index("ix_invoice_items_invoice_id", table_name="invoice_items")
